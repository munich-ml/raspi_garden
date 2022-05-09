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


# switches randy according to state
def switch_randy(state):
    if state:
        gpio.output(PIN_RANDY, gpio.HIGH)
    else:
        gpio.output(PIN_RANDY, gpio.LOW)
            

if __name__ == "__main__":
    initialize_gpios()
    turn_off_all_gpios()
    switch_randy(True)
