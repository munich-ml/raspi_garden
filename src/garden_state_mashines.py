# -*- coding: utf-8 -*-
"""
Created on Sat Aug 18 07:44:29 2018

@author: holge
"""

import os
import time
import datetime as dt 
import RPi.GPIO as gpio    
import Adafruit_DHT as Ada
from enum import Enum
from threading import Thread
from garden_utilities import globalLogger as logger


# --------- Pinning --------- 
BUTTON_GO = 19
BUTTON_BACK = 6
PIN_LED_RED = 23
PIN_LED_GREEN = 25
PIN_SP_NORTH = 8    # MISO
PIN_SP_EAST = 10    # MOSI
PIN_SP_WEST = 9     # CS0
PIN_RANDY = 7       # CS1
SENSOR_INT = 20
SENSOR_EXT = 26

OUTPUTS = (PIN_LED_RED, PIN_LED_GREEN, PIN_SP_NORTH, PIN_SP_WEST, PIN_SP_EAST,
           PIN_RANDY)
SPRINKLERS = (PIN_SP_NORTH, PIN_SP_WEST, PIN_SP_EAST)
LEDS = (PIN_LED_RED, PIN_LED_GREEN)
INPUTS = (BUTTON_GO, BUTTON_BACK, SENSOR_INT, SENSOR_EXT)


def initialize_gpios():
    gpio.setwarnings(False)
    gpio.setmode(gpio.BCM)
    for pin in OUTPUTS:
        gpio.setup(pin, gpio.OUT)
    
    for pin in INPUTS:
        gpio.setup(pin, gpio.IN, pull_up_down=gpio.PUD_OFF)

    turn_off_all_gpios()
    

def turn_off_all_gpios():
    for pin in OUTPUTS:
        gpio.output(pin, gpio.LOW)


# switches sprinklers according to states
# input states <iterable> of length=3. e.g.:(True, False, False) for North, West, East
def switch_sprinkler(states):
    for sprinkler, state in zip(SPRINKLERS, states):
        if state:
            gpio.output(sprinkler, gpio.HIGH)
        else:
            gpio.output(sprinkler, gpio.LOW)
            

# switches randy according to state
def switch_randy(state):
    if state:
        gpio.output(PIN_RANDY, gpio.HIGH)
    else:
        gpio.output(PIN_RANDY, gpio.LOW)
            

# possible states of button scan (inkl. blink codes)
class State(Enum):
    PWDN = 20
    ABOUT_TO_PWDN  = ("01", "00")
    ASLEEP = 21
    ABOUT_TO_WAKEUP = 22
    AWAKE          = ("10000000", "00000000")
    ABOUT_TO_RANDOM= ("00000000", "10100000")
    RANDOM         = ("00000000", "01011111")
    ABOUT_TO_RAIN  = ("00000000", "10000000")
    RAINING        = ("00000000", "01111111")
    ABOUT_TO_LOAD  = ("00000000", "10101000")
    LOADING        = ("00000000", "01010111")


# returns a string of temp / hum readings
def scan_local_sensors():
    # step 1: read CPU temperature
    tempCPU = os.popen('vcgencmd measure_temp').readline()
    s = "\n\tCPU T=" + tempCPU.replace("temp=","").replace("'C\n","") + "°C"
    
    # step 2: read temp / humidity sensors
    for sensor, label in zip((SENSOR_INT, SENSOR_EXT), ("\n\tint ", "\n\text ")):
        try:
            hum, temp = Ada.read_retry(Ada.AM2302, sensor)    
            s += label + "T={0:4.1f}°C, RH={1:4.1f}%".format(temp, hum)
        except Exception as e:
            s += label + "!Exception occured: " + str(e)
    return s


# Main state mashine
class MainStateMashine():
    def __init__(self, SHORT_BUTTON_PRESS, LONG_BUTTON_PRESS, PWDN_TIMEOUT, INACT_TIMEOUT):
        self.PWDN_TIMEOUT = PWDN_TIMEOUT    # power down timeout constant
        self.pwdnTimeout = dt.datetime.now() + dt.timedelta(999,0,0)   # power down timeout variable
        self.INACT_TIMEOUT = INACT_TIMEOUT    # inactivity timeout constant
        self.inactTimeout = dt.datetime.now() + dt.timedelta(999,0,0)   # inactivity timeout variable
        self.state = State.ASLEEP
        self.goStateMashine = GoButtonStateMashine(SHORT_BUTTON_PRESS, LONG_BUTTON_PRESS)
        self.backStateMashine = BackButtonStateMashine(LONG_BUTTON_PRESS)  
        
    
    def _set_state_ASLEEP(self):
        self._kill_led_timer()
        self.state = State.ASLEEP
        
    def _set_state_ABOUT_TO_WAKEUP(self):
        self._create_led_timer()
        self.state = State.ABOUT_TO_WAKEUP
        
    def _set_state_AWAKE(self):
        self.state = State.AWAKE
        self.ledTimer.setSequences(State.AWAKE.value)
        self.inactTimeout = dt.datetime.now() + self.INACT_TIMEOUT
    
    def _set_state_ABOUT_TO_RAIN(self):
        self.state = State.ABOUT_TO_RAIN
        self.ledTimer.setSequences(State.ABOUT_TO_RAIN.value)
        self.inactTimeout = dt.datetime.now() + self.INACT_TIMEOUT

    def _set_state_RAINING(self):
        self.state = State.RAINING
        self.ledTimer.setSequences(State.RAINING.value)
        
    def _set_state_ABOUT_TO_RANDOM(self):
        self.state = State.ABOUT_TO_RANDOM
        self.ledTimer.setSequences(State.ABOUT_TO_RANDOM.value)
        self.inactTimeout = dt.datetime.now() + self.INACT_TIMEOUT
    
    def _set_state_RANDOM(self):
        self.state = State.RANDOM
        self.ledTimer.setSequences(State.RANDOM.value)
        
    def _set_state_ABOUT_TO_LOAD(self):
        self.state = State.ABOUT_TO_LOAD
        self.ledTimer.setSequences(State.ABOUT_TO_LOAD.value)
        self.inactTimeout = dt.datetime.now() + self.INACT_TIMEOUT

    def _set_state_LOADING(self):
        self.ledTimer.setSequences(State.LOADING.value)
        self.state = State.LOADING

    def _set_state_ABOUT_TO_PWDN(self):
        self.pwdnTimeout = dt.datetime.now() + self.PWDN_TIMEOUT
        self.ledTimer.setSequences(State.ABOUT_TO_PWDN.value)
        self.state = State.ABOUT_TO_PWDN
                
    def _set_state_PWDN(self):
        self._kill_led_timer()
        self.state = State.PWDN

    def _create_led_timer(self):
        self.ledTimer = LedTimer(leds=LEDS)
        self.ledTimer.start()
        time.sleep(0.01)
        
    def _kill_led_timer(self):
        self.ledTimer.stop()
        time.sleep(0.01)

    # update state depending on previous state and buttons
    def update(self):
        # scan buttons and update the mainStateMashine
        goButton = not(gpio.input(BUTTON_GO))
        backButton = not(gpio.input(BUTTON_BACK))

        # simple (button-state-based) wakeup encoding in case of a sleeping system
        if self.state == State.ASLEEP:
            if goButton or backButton:
                self._set_state_ABOUT_TO_WAKEUP()
            return
        elif self.state == State.ABOUT_TO_WAKEUP:
            if not goButton and not backButton:
                self._set_state_AWAKE()
            return
        
        # simple (button-state-based) power-down encoding 
        elif self.state == State.ABOUT_TO_PWDN:
            if backButton:
                if dt.datetime.now() > self.pwdnTimeout:    
                    self._set_state_PWDN()
            else:
                self._set_state_AWAKE()
            return
                
        # regular (event-based) state encoding for any wake state
        else:    
            goEvent = self.goStateMashine.update(goButton)
            backEvent = self.backStateMashine.update(backButton)
            if goEvent != ButtonEvent.NONE or backEvent != ButtonEvent.NONE:
                # logger.info("state=" + str(self.state) + "\tgo=" + str(goEvent) + 
                #            "\tback=" + str(backEvent))
                if self.state == State.AWAKE:
                    if goEvent == ButtonEvent.SINGLE:
                        self._set_state_ABOUT_TO_RAIN()
                    elif goEvent == ButtonEvent.DOUBLE:
                        self._set_state_ABOUT_TO_RANDOM()
                    elif goEvent == ButtonEvent.TRIPPLE:
                        self._set_state_ABOUT_TO_LOAD()
                    elif backEvent == ButtonEvent.LONG:
                        self._set_state_ABOUT_TO_PWDN()
                elif self.state == State.ABOUT_TO_RAIN:
                    if goEvent == ButtonEvent.LONG:
                        self._set_state_RAINING()
                    elif backEvent == ButtonEvent.SINGLE:
                        self._set_state_AWAKE()
                elif self.state == State.RAINING:
                    if backEvent == ButtonEvent.SINGLE:
                        self._set_state_AWAKE()
                elif self.state == State.ABOUT_TO_RANDOM:
                    if goEvent == ButtonEvent.LONG:
                        self._set_state_RANDOM()
                    elif backEvent == ButtonEvent.SINGLE:
                        self._set_state_AWAKE()
                elif self.state == State.RANDOM:
                    if backEvent == ButtonEvent.SINGLE:
                        self._set_state_AWAKE()
                elif self.state == State.ABOUT_TO_LOAD:
                    if goEvent == ButtonEvent.LONG:
                        self._set_state_LOADING()
                    elif backEvent == ButtonEvent.SINGLE:
                        self._set_state_AWAKE()
                elif self.state == State.LOADING:
                    if backEvent == ButtonEvent.SINGLE:
                        self._set_state_AWAKE()
                else:
                    logger.error("Unknown state: " + str(self.state))

            else: # no ButtonEvent --> check for inactivity
                if not goButton and not backButton:
                    if dt.datetime.now() > self.inactTimeout:
                        if self.state == State.AWAKE:
                            self._set_state_ASLEEP()
                        elif self.state == State.ABOUT_TO_RAIN:
                            self._set_state_AWAKE()
                        elif self.state == State.ABOUT_TO_RANDOM:
                            self._set_state_AWAKE()
                        elif self.state == State.ABOUT_TO_LOAD:
                            self._set_state_AWAKE()
        
        
# Possible events from button state mashines
class ButtonEvent(Enum):
    NONE = 0
    SINGLE = 1
    DOUBLE = 2
    TRIPPLE = 3
    LONG = 4


# state mashine for back button
class BackButtonStateMashine():
    def __init__(self, LONG_BUTTON_PRESS):
        self.LONG_BUTTON_PRESS = LONG_BUTTON_PRESS
        self.state = 0
        self.longTimeout = dt.datetime.now() + dt.timedelta(999,0,0)
        self.shortTimeout = dt.datetime.now() + dt.timedelta(999,0,0)
        
    def update(self, current_button):
        if self.state == 0:
            if current_button:
                self.state = 1
                self.longTimeout = dt.datetime.now() + self.LONG_BUTTON_PRESS
            return ButtonEvent.NONE
        
        elif self.state == 1:
            if current_button:
                if dt.datetime.now() > self.longTimeout:
                    self.state = 2
                    return ButtonEvent.LONG
                else:
                    return ButtonEvent.NONE
            else:
                self.state = 0
                return ButtonEvent.SINGLE    
                
        elif self.state == 2:
            if not current_button:
                self.state = 0
            return ButtonEvent.NONE
            
        else:
            logger.error("Unknown BackButtonStateMashine.state " + str(self.state))
        

# state mashine for go button
class GoButtonStateMashine():
    def __init__(self, SHORT_BUTTON_PRESS, LONG_BUTTON_PRESS):
        self.SHORT_BUTTON_PRESS = SHORT_BUTTON_PRESS
        self.LONG_BUTTON_PRESS = LONG_BUTTON_PRESS
        self.state = 0
        self.longTimeout = dt.datetime.now() + dt.timedelta(999,0,0)
        self.shortTimeout = dt.datetime.now() + dt.timedelta(999,0,0)
        
    def update(self, current_button):
        if self.state in [1, 3, 5]:
            if current_button:
                if dt.datetime.now() > self.longTimeout:
                    self.state = 7
                    return ButtonEvent.LONG
                else:
                    return ButtonEvent.NONE
            else:
                self.state += 1
                self.shortTimeout = dt.datetime.now() + self.SHORT_BUTTON_PRESS
                return  ButtonEvent.NONE

        elif self.state in [0,2,4,6]:
            if current_button:
                self.state += 1
                self.longTimeout = dt.datetime.now() + self.LONG_BUTTON_PRESS
                return ButtonEvent.NONE
            else:
                if dt.datetime.now() > self.shortTimeout:
                    if self.state == 2:
                        event = ButtonEvent.SINGLE
                    elif self.state == 4:
                        event = ButtonEvent.DOUBLE
                    elif self.state == 6:
                        event = ButtonEvent.TRIPPLE
                    else:
                        event = ButtonEvent.NONE
                    self.state = 0
                    return event
                else:
                    return ButtonEvent.NONE
        elif self.state == 7:
            if not current_button:
                self.state = 0
            return ButtonEvent.NONE
            
        else:
            logger.error("Unknown GoButtonStateMashine.state " + str(self.state))
     

# Timer for blinking sequences of the LEDs
class LedTimer(Thread):
    def __init__(self, leds, t=0.12):
        super(LedTimer, self).__init__()
        self.t = t
        self.leds = leds
        self.pointer  = 0
        self.running = True
        self.setSequences()

    def setSequences(self, seqRedGreen=("1000", "0100")):
        self.seqRed   = seqRedGreen[0]
        self.seqGreen = seqRedGreen[1]
        self.pointer  = 0
        
    def _setLedOutputs(self, states):
        for led, state in zip(self.leds, states):
            if state == "1":
                gpio.output(led, gpio.HIGH)
            else:
                gpio.output(led, gpio.LOW)

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            tStart = time.time()
            red   = self.seqRed[self.pointer]
            green = self.seqGreen[self.pointer]
            #print("rgb=" + red + green )
            self._setLedOutputs((red, green))
            
            self.pointer += 1
            if self.pointer >= len(self.seqRed):
                self.pointer = 0
            tElapsed = time.time()-tStart
            time.sleep(max(0, self.t - tElapsed))
        
        # exiting
        self._setLedOutputs("00")
        logger.info("exiting LedTimer thread")

        

class RandyPauseDaysCounter():
    def __init__(self, pauseSet = 0):
        self.pauseSet = pauseSet
        self._pauseCtr = 0
    
    # returns True to mow and False to not mow
    def get_update(self):
        if self._pauseCtr >= self.pauseSet:
            self._pauseCtr = 0
            return True
        else:
            self._pauseCtr += 1
            return False
            
            
            
            
            
            