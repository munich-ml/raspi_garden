# -*- coding: utf-8 -*-
"""
Created on Mon Aug 20 20:47:30 2018

@author: holge
"""

import logging


# logging logger
def get_logger(filename):
    # create logger with 'spam_application'
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # create file handler which logs even debug messages
    fh = logging.FileHandler(filename)
    fh.setLevel(logging.INFO)
    
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


globalLogger = get_logger('raspi_garden.log')




if __name__ == "__main__":
    print("Testing garden_utilities.py ...")
    allSettings = ControlFileReader.read("control.txt")
    print(allSettings)
    
    