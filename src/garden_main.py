# -*- coding: utf-8 -*-
"""
Created on Mon Aug 13 20:22:57 2018

@author: holge
"""

import datetime as dt
from time import sleep
from garden_state_mashines import MainStateMashine, State, initialize_gpios
from garden_state_mashines import switch_sprinkler, switch_randy, turn_off_all_gpios
from garden_state_mashines import scan_local_sensors, RandyPauseDaysCounter
from garden_utilities import globalLogger as logger
from garden_jobs import JKey, Job, JobQueue, ControlFileReader
from PiUSV import Usv
from weather_owm import get_weather_forcast

# constants
TIME_DAILY_INIT = dt.time(0,0,0)    # DON'T CHANGE FROM 0:00. Every day at this time, the control.txt is loaded
PERIOD_BUTTON_SCAN_ASLEEP = dt.timedelta(0,5)       # Period of scanning the buttons in State.ASLEEP
PERIOD_BUTTON_SCAN_AWAKE = dt.timedelta(0,0,50000)  # Period of scanning the buttons in State.AWAKE
PERIOD_LOCAL_SENSOR_SCAN = dt.timedelta(0,3600)     # Period of scanning the local temperature and humidity
PERIOD_PIUSV_SCAN = dt.timedelta(0,20)              # Period of scanning the PiUSV for power outage
TIME_TO_FIRST_SENSOR_SCAN = dt.timedelta(0,10,0)    # After this time the local temperature and humidity sensors are scanned the first time
SHORT_BUTTON_PRESS = dt.timedelta(0,0,500000)       # After this time (from releasing the button) the ButtonEvent (single, double, tripple) is emitted
LONG_BUTTON_PRESS = dt.timedelta(0,1,200000)        # After this time a button press is recognized as long button presss
PWDN_TIMEOUT = dt.timedelta(0,4,0)                  # How long to keep back-button pressed in State.ABOUT_TO_PWDN before it actually powers down
INACT_TIMEOUT = dt.timedelta(0,20,500000)           # Return to next lower state after this time of button inactivity
SPRINKLER_PAUSE = dt.timedelta(0,2,0)               # Wait time between two spinkler events
WEATHER_OWM_RETRY = dt.timedelta(0,60,0)            # Wait time to the next weather acquisition time
RANDY_RAIN_INHIBIT = 0.15                           # rain [mm/h] limit for randy to mow
RANDY_PAUSE_DAYS = 1

class MainGardenClass():
    def __init__(self):
        self.mainState = MainStateMashine(SHORT_BUTTON_PRESS, LONG_BUTTON_PRESS, 
                                          PWDN_TIMEOUT, INACT_TIMEOUT)
        self.usv = Usv()
        self.randyPauseCntr = RandyPauseDaysCounter(RANDY_PAUSE_DAYS)
        self.currentJob = False
        self.jobQueue = JobQueue()

        # put initial jobs
        self.jobQueue.put(Job.gen_daily_init_job(dt.datetime.now()))
        self.jobQueue.put(Job.gen_button_scan_job(self.mainState, PERIOD_BUTTON_SCAN_ASLEEP, PERIOD_BUTTON_SCAN_AWAKE))
        self.jobQueue.put(Job.gen_local_sensor_scan_job(TIME_TO_FIRST_SENSOR_SCAN))
        self.jobQueue.put(Job.gen_piusv_scan_job(PERIOD_PIUSV_SCAN))
        
    
    def check_usv(self):
        sdr, log = self.usv.check_stats_and_values()
        if log:
            logger.info(str(self.currentJob.key) + log)
        if sdr:  # shut down request
            self.shut_down()
                            
                            
    def shut_down(self):
        self.usv.shut_down()
        logger.info("++++++++++ shutting down ++++++++++")
        while True:
            sleep(1)
            self.check_usv()
            logger.info("shutdown ongoing ...")        
        
        
if __name__ == "__main__":

    logger.info("++++++++++ starting up ++++++++++")
    initialize_gpios()
  
    mg = MainGardenClass()
    weatherForecast = None
    
    try:
        while True:
            if mg.jobQueue.empty():    
                logger.error("jobQueue is empty!")
                break
            else:
                if mg.currentJob: # not entered the very first time
                    curKey = mg.currentJob.key
                    if curKey == JKey.BUTTONS:
                        # scan buttons and update the mainStateMashine
                        mg.mainState.update()

                        # schedule and put the next button scan job
                        mg.jobQueue.put(Job.gen_button_scan_job(mg.mainState.state, 
                            PERIOD_BUTTON_SCAN_ASLEEP, PERIOD_BUTTON_SCAN_AWAKE))

                    elif curKey == JKey.WEATHER_OWM:
                        success, trials, wfTmp = get_weather_forcast()
                        if success:
                            weatherForecast = wfTmp
                            logger.info("{} succeeded\n{}".format(curKey, weatherForecast))
                        else:
                            logger.info("{} failed after {} trials.".format(curKey, trials))
                            nextTrial = dt.datetime.now() + WEATHER_OWM_RETRY
                            mg.jobQueue.put(Job.gen_weather_owm_job(nextTrial))
                            

                    elif curKey == JKey.LOCAL_SENSOR:
                        # schedule and put the next local sensor scan job
                        mg.jobQueue.put(Job.gen_local_sensor_scan_job(PERIOD_LOCAL_SENSOR_SCAN))
                        
                        # log local sensor readings
                        logger.info(str(curKey) + scan_local_sensors())                        
                        
                    elif curKey == JKey.PIUSV:
                        # schedule and put the next PiUSV scan job
                        mg.jobQueue.put(Job.gen_piusv_scan_job(PERIOD_PIUSV_SCAN))
                        
                        mg.check_usv()
                        
                    elif curKey == JKey.SWITCH_SPRINKLER:
                        logger.info(str(mg.currentJob))
                        switch_sprinkler(mg.currentJob.params)

                    elif curKey == JKey.SWITCH_RANDY:
                        mowOrCharge, on = mg.currentJob.params
                        doSwitching = True
                        if mowOrCharge == "mow":     # do all "charge" switchings 
                            if on:                   # do all "off" switchings
                                if weatherForecast is None:
                                    doSwitching = False
                                    mg.randyPauseCntr._pauseCtr += 1
                                    logger.warning("No mowing because weatherForecast is None!")
                                else:
                                    rain = weatherForecast.get_rain_at_daytime(dt.datetime.now().date())
                                    if rain is None:
                                        doSwitching = False
                                        mg.randyPauseCntr._pauseCtr += 1
                                        logger.warning("No mowing because weatherForecastget_rain_at_daytime() returned None!")
                                    else:
                                        if rain > RANDY_RAIN_INHIBIT:
                                            doSwitching = False
                                            mg.randyPauseCntr._pauseCtr += 1
                                            logger.info("No mowing because of rain: {0:0.2f}".format(rain))
                                        else:
                                            if not mg.randyPauseCntr.get_update():    # do not mow on pause days
                                                doSwitching = False
                        
                        if doSwitching:
                            logger.info(str(curKey) + ", " + str(mg.currentJob.params))
                            switch_randy(on)

                    elif curKey == JKey.DAILY_INIT:
                        logger.info(str(curKey) + ": JobQueue before loading control.txt:\n" + str(mg.jobQueue))
                        ControlFileReader.put_all_new_jobs(mg.jobQueue)
                        mg.jobQueue.put(Job.gen_daily_init_job(TIME_DAILY_INIT))
                        logger.info(str(curKey) + ": JobQueue afterwards:\n" + str(mg.jobQueue))

                    else:
                        logger.error("main: Unknown current job: " + str(mg.currentJob))
                
                # do actions according to current state
                if mg.mainState.state == State.PWDN:
                    logger.info("powering down")
                    break                    
                
                elif mg.mainState.state == State.RAINING: 
                    logger.info("manual raining initiated")
                    ControlFileReader.put_new_sprinkler_jobs(mg.jobQueue, buttonNow=True)
                    mg.mainState._set_state_AWAKE()
                    
                elif mg.mainState.state == State.LOADING: 
                    logger.info("State.LOADING: JobQueue before loading control.txt:\n" + str(mg.jobQueue))
                    ControlFileReader.put_all_new_jobs(mg.jobQueue)
                    logger.info("State.LOADING: JobQueue afterwards:\n" + str(mg.jobQueue))
                    mg.mainState._set_state_AWAKE()
                
                # get next job from job queue 
                mg.currentJob = mg.jobQueue.get()
                
                # sleep until next job
                tSleep = (mg.currentJob.t - dt.datetime.now()).total_seconds()
                sleep(max(0, tSleep))

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")

    except Exception as e:
        logger.error("Exception in main loop:\n" + str(e))
    
    finally:
        turn_off_all_gpios()
        mg.shut_down()

    
