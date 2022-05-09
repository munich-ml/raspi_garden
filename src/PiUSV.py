# -*- coding: utf-8 -*-
"""
Created on Sat Apr  6 20:35:00 2019

@author: holge
"""

import smbus
import numpy as np
from time import sleep
from garden_utilities import globalLogger as logger

I2C_ADR = 0x18

USV_STATUS = 0x00
USV_VERSION = 0x01
USV_VALUES = 0x02

# Plausibility check limits
USV_VALUES_PLAUSI = ((3000, 5000),  # battery voltage, typ. 3.7V
                     (100, 1200),   # output current to the raspi, ~400mA 
                     (3500, 6500),  # output voltage to the raspi, 5V
                     (0, 6500),     # usb input voltage, typ. 5V
                     (0, 30000))    # wide-range input voltage 5..25V

USV_SHUTDOWN = 0x10
USV_SHUTDOWN_TIME = 10   # in seconds

USV_MAX_RETRIES = 20
USV_RETRY_PAUSE = 0.1

USV_MIN_VBATTERY = 3800


class I2C_device:
    def __init__(self, addr, port=1):
        self.addr = addr
        self.bus = smbus.SMBus(port)   

    # Write a single command
    def write_cmd(self, cmd):
        self.bus.write_byte(self.addr, cmd)
        sleep(0.0001)

    # Read a single byte
    def read(self):
        return self.bus.read_byte(self.addr)



class Usv:
    @staticmethod
    def values_to_string(vals):
        s = ""
        names = ("Vbat", "Ipi", "Vpi", "Vext", "Vusb")
        units = ("mV", "mA", "mV", "mV", "mV")
        for name, val, unit in zip(names, vals, units):
            s += "\n\t{0}={1:.0f}{2}".format(name, val, unit)
        return s
    
    
    def __init__(self):
        self.device = I2C_device(I2C_ADR)
        sleep(0.2)
    
    # returns <int> status
    # 1: battery fully charged
    # 2: battery operation    
    # 9: battery charging
    def read_status(self):
        try:
            self.device.write_cmd(USV_STATUS)
            return self.device.read()
        except Exception as e:
            logger.error("Exception in usv.read_status(). " + str(e))
            return None
    
    # returns <list> values:
    # values[0]: Vbat [V], battery voltage, typ. 3.7V
    # values[1]: Ipi  [mA], output current to the raspi, ~400mA 
    # values[2]: Vpi  [V], output voltage to the raspi, 5V 
    # values[3]: Vext [V], wide-range input voltage 5..25V
    # values[4]: Vusb [V], usb input voltage, 5V
    # values[5]: plausible <bool>, True if values are plausible
    def read_values(self):
        try:
            self.device.write_cmd(USV_VALUES)
            values = []
            plausible = True
            for plausiLimits in USV_VALUES_PLAUSI:
                # step 1: Read value has highByte, lowByte from PiUSV
                high = self.device.read()
                low = self.device.read()
                val = (high << 8) + low
                
                # step 2: Check for plausibility
                if val < plausiLimits[0] or val > plausiLimits[1]:
                    plausible = False
                
                # step 3: append new value
                values.append(val)
                
            # append plausibility at values[5]
            values.append(plausible)
            return values
        
        except Exception as e:
            logger.error("Exception in usv.read_values(). " + str(e))
            return None
        
    
    # returns <list> average values:
    # input <int> num, number of averages
    def read_avg_values(self, num=5):
        stacks = [[],[],[],[],[]]
        retries = 0
        
        # step 1: Acquire data
        while len(stacks[0]) < num:
            vals = self.read_values()
            plausible = vals.pop(-1)
            if plausible:
                for stack, val in zip(stacks, vals):
                    stack.append(val)
            else:
                retries += 1
                if retries > USV_MAX_RETRIES:
                    return None
            sleep(USV_RETRY_PAUSE)
        
        # step 2: Compute average
        averages = list()
        for stack in stacks:
            nStack = np.array(stack)
            if len(nStack) > 3:                 # cut off extreme 50% of the values
                cutoff = int(len(nStack) / 4)
                nStack.sort()
                nStack = nStack[cutoff:-cutoff]
            averages.append(nStack.mean())    
                
        return averages
    
    
    # returns <tuple> (sdr, log), sdr <bool> shut down request
    #                             log <str>, empty "" if no log
    def check_stats_and_values(self):
        log = ""      # log message
        sdr = True    # shut down request
            
        # step 1: Read status
        retries = 0
        while True:
            status = self.read_status()
            if status is None:
                retries += 1
                if retries > USV_MAX_RETRIES:
                    status = "PiUSV did not respond to read_status()"
                    break
            else:
                if status != 2:   # battery operation
                    sdr = False
                break
            
        # step 2: Read values        
        if sdr:
            log += "\n\tstatus=" + str(status)
            vals = self.read_avg_values()
            if vals is None:
                log += "\n\tPiUSV did not respond to read_values()"
            else:
                vBat = vals[0]
                if vBat > USV_MIN_VBATTERY:
                    sdr = False    # no immidiate shutdown required
                log += Usv.values_to_string(vals)
                log += "\n\tshutdown request=" + str(sdr)
                
        return(sdr, log)
    
    
    # The PiUSV (not the RasPi) will shut down after ~20s
    def shut_down(self):
        try:
            self.device.write_cmd(USV_SHUTDOWN)
        except self.on as e:
            logger.error("Exception in usv.shut_down(). " + str(e))
        
        
    
if __name__ == "__main__":
    import datetime as dt
    usv = Usv()
    while True:
        ### read stats
        stats = usv.read_status()
        print("stats={} of type {}".format(stats, type(stats)))        
        
        ### read values
        t0 = dt.datetime.now()
        data = usv.read_avg_values(num=5)
        tDelta = dt.datetime.now() - t0
        print("usv.read_avg_values() took {:.2f}s".format(tDelta.total_seconds()))
        if data is None:
            print("Waring: None returned!")
        else:
            print(str(t0) + Usv.values_to_string(data))
        sleep(1)
    