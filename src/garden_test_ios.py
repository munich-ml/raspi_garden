# -*- coding: utf-8 -*-
"""
Created on Sat Aug 18 07:44:29 2018

@author: holge
"""


from time import sleep
import RPi.GPIO as gpio    # uncommented for offline test

import Adafruit_DHT as Ada


# --------- Pinning --------- 
BUTTON_GO = 19
BUTTON_BACK = 6
PIN_LED_RED = 23
PIN_LED_GREEN = 25
PIN_SP_NORTH = 9    # MISO
PIN_SP_EAST = 10    # MOSI
PIN_SP_WEST = 8     # CS0
PIN_RANDY = 7       # CS1
SENSOR_INT = 20
SENSOR_EXT = 26

OUTPUTS = (PIN_LED_RED, PIN_LED_GREEN, PIN_SP_NORTH, PIN_SP_WEST, PIN_SP_EAST,
           PIN_RANDY)
INPUTS = (BUTTON_GO, BUTTON_BACK, SENSOR_INT, SENSOR_EXT)

def initialize_gpios():
    gpio.setwarnings(False)
    gpio.setmode(gpio.BCM)
    for pin in OUTPUTS:
        gpio.setup(pin, gpio.OUT)
        gpio.output(pin, gpio.LOW)
    
    for button in INPUTS:
        gpio.setup(button, gpio.IN, pull_up_down=gpio.PUD_OFF)

if __name__ == "__main__":
    initialize_gpios()
    
    while True:
        sleep(0.1)
        
        goButton = not(gpio.input(BUTTON_GO))
        backButton = not(gpio.input(BUTTON_BACK))

        # relay action
        if goButton:
            gpio.output(PIN_LED_GREEN, gpio.HIGH)
            gpio.output(PIN_LED_RED, gpio.LOW)
            pins = (PIN_SP_NORTH, PIN_SP_WEST, PIN_SP_EAST, PIN_RANDY)
            for pin in pins:
                gpio.output(pin, gpio.HIGH)
                sleep(1)
            for pin in pins:
                gpio.output(pin, gpio.LOW)
        
        # sensor test        
        elif backButton:
            gpio.output(PIN_LED_GREEN, gpio.LOW)
            gpio.output(PIN_LED_RED, gpio.HIGH)
            for sensor, label in zip((SENSOR_INT, SENSOR_EXT), ("Internal", "External")):
                hum, temp = Ada.read_retry(Ada.AM2302, sensor)
                if hum is not None and temp is not None:
                    print(label + ": " + str(temp) + "°C, " + str(hum) + "%RH")
                else:
                    print(label + " reading failed")
        
        else:
            gpio.output(PIN_LED_GREEN, gpio.LOW)
            gpio.output(PIN_LED_RED, gpio.LOW)
