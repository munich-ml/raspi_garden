# -*- coding: utf-8 -*-
"""
Created on Mon Aug 20 20:47:30 2018

@author: holge
"""

import datetime as dt
from enum import Enum
from garden_state_mashines import State, MainStateMashine
from garden_utilities import globalLogger as logger

from queue import PriorityQueue


CONTROL_FILENAME = "control.txt"
TIME_DAILY_INIT = dt.time(0,0,0)    # DON'T CHANGE FROM 0:00. Every day at this time, the control.txt is loaded
SPRINKLER_PAUSE = dt.timedelta(0,2,0)        # Wait time between two spinkler events

# A job from Job() hold the time, a JKey and params. 
# A job will be stored in the jobQueue
class Job():
    def __init__(self, t, key, params=None):
        self.t = t
        self.key = key
        self.params = params
        
    def __str__(self):
        s = dt.datetime.strftime(self.t, "%Y-%m-%d %H:%M:%S.%f")
        s += ", " + str(self.key) + ", " + str(self.params)
        return s
    
    # "less than" implementation. Required for compares. Required for PriorityQueue
    def __lt__(self, other):
        return self.t < other.t
        
    def __le__(self, other):
        return self.t <= other.t
        
    def __gt__(self, other):
        return self.t > other.t
        
    def __ge__(self, other):
        return self.t >= other.t
    
    # Job constructor for the next button scan
    @staticmethod
    def gen_button_scan_job(state, period_asleep, period_awake):
        if state == State.ASLEEP:
            t = dt.datetime.now() + period_asleep
        else:
            t = dt.datetime.now() + period_awake
            
        return Job(t, JKey.BUTTONS, None)

    # Job constructor for the next local sensor scan job
    @staticmethod
    def gen_local_sensor_scan_job(period):
        return Job(dt.datetime.now() + period, JKey.LOCAL_SENSOR, None)

    # Job constructor for the next PiUSV scan job
    @staticmethod
    def gen_piusv_scan_job(period):
        return Job(dt.datetime.now() + period, JKey.PIUSV, None)

    # Job constructor for a switch randy
    @staticmethod
    def gen_randy_switch_job(switchTime, on):
        if type(switchTime) == dt.time:
            today = dt.datetime.now().date()
            t = dt.datetime.combine(today, switchTime)
        elif type(switchTime) == dt.datetime:
            t = switchTime
        return Job(t, JKey.SWITCH_RANDY, on)

    # Job constructor for a weather OWM job
    @staticmethod
    def gen_weather_owm_job(aquTime):
        if type(aquTime) == dt.time:
            today = dt.datetime.now().date()
            t = dt.datetime.combine(today, aquTime)
        elif type(aquTime) == dt.datetime:
            t = aquTime
        return Job(t, JKey.WEATHER_OWM, None)

    # Job constructor for tomorrows daily init
    @staticmethod
    def gen_daily_init_job(timeDailyInit):
        # Case 1: Used for daily init
        if type(timeDailyInit) == dt.time:
            tomorrow = dt.datetime.now().date() + dt.timedelta(1)
            t = dt.datetime.combine(tomorrow, timeDailyInit)
            return Job(t, JKey.DAILY_INIT, None)

        # Case 2: Used for initial init
        else:
            return Job(timeDailyInit, JKey.DAILY_INIT, None)
    
# possible job keys for jobQueue
class JKey(Enum):
    BUTTONS = 1
    WEATHER_OWM = 2
    LOCAL_SENSOR = 3
    SWITCH_SPRINKLER = 4
    SWITCH_RANDY = 5
    DAILY_INIT = 6   
    PIUSV = 7      


# Queue for Jobs (e.g. scan buttons)
class JobQueue(PriorityQueue):
    def __init__(self):
        PriorityQueue.__init__(self)
        
    def __str__(self):
        cpy = []
        while not self.empty():
            cpy.append(self.get())
        s = "\tJobQueue, size=" + str(len(cpy))
        for i, job in enumerate(cpy):
            s += "\n\t" + str(i+1) + ": " + str(job)
            self.put(job)
        return s

# class holding the settings related to randy
class RandySettings():
    def __init__(self):
        self.chargeOn = False
        self.chargeOff= False
        self.mowOn = False
        self.mowOff= False
        self.pauseDays = 0.0
        self.rainInhibit = False
        self.windInhibit = False
        self.sprinklerInhibit = False
        
    def __str__(self):
        s = "charge=" + str(self.chargeOn) + ".." + str(self.chargeOff)
        s+= ", mow=" + str(self.mowOn) + ".." + str(self.mowOff)
        s+= ", pauseDays=" + str(self.pauseDays)
        s+= ", rainInh=" + str(self.rainInhibit)
        s+= ", windInh=" + str(self.windInhibit)
        s+= ", sprinklerInh=" + str(self.sprinklerInhibit)
        return s

# class holding the settings related to the sprinklers
class SprinklerSettings():
    def __init__(self):
        self.north = False
        self.west  = False
        self.east = False
        self.schedules = []
        self.windInhibit = False
        
    def __str__(self):
        s = "north=" + str(self.north) 
        s+= ", west=" + str(self.west)
        s+= ", east=" + str(self.east)
        s+= ", windInh=" + str(self.windInhibit)
        for schedule in sorted(self.schedules):
            s+= ", " + str(schedule) 
        return s

# class holding all settings
class AllSettings():
    def __init__(self):
        self.randy = RandySettings()
        self.sprinkler = SprinklerSettings()
        self.weatherOwm = False
        self.localSensors = []
        
    def __str__(self):
        s = "AllSettings:"
        s+= "\n(1) randy: " + str(self.randy)
        s+= "\n(2) sprinkler: " + str(self.sprinkler)
        s+= "\n(3) weather OWM: " + str(self.weatherOwm)
        s+= "\n(4) local sensors: ["
        for date in self.localSensors:
            s+= str(date) + ", "
        s = s[:-2] + "]"
        return s        

# control.txt reader class
class ControlFileReader():
    @staticmethod
    def __hhmmssToTimedelta(hhmmss):
        # expects hh:mm:ss or mm:ss or mm inputs
        blks = str(hhmmss).split(":")
        if len(blks) == 1:
            secs = 60*int(blks[0])
        elif len(blks) == 2:
            secs = 60*int(blks[0]) + int(blks[1])
        else:
            secs = 60* (60*int(blks[0]) + int(blks[1])) + int(blks[2])
        return dt.timedelta(0, secs, 0)
    
    # returns a AllSettings object from a control file
    @staticmethod    
    def __read():
        file = open(CONTROL_FILENAME, "r")
        allSettings = AllSettings()
        for line in file:
            if len(line) > 8 and line[0] != "#":  # then the line should contain content
                items = line.strip().split(" ")
                key = items[0]
                if key == "RandyChargeTime":
                    allSettings.randy.chargeOn  = dt.datetime.strptime(items[1], '%H:%M:%S').time()
                    allSettings.randy.chargeOff = dt.datetime.strptime(items[2], '%H:%M:%S').time()
                elif key == "RandyMowTime":
                    allSettings.randy.mowOn  = dt.datetime.strptime(items[1], '%H:%M:%S').time()
                    allSettings.randy.mowOff = dt.datetime.strptime(items[2], '%H:%M:%S').time()
                elif key == "RandyPauseDays":
                    allSettings.randy.pauseDays = float(items[1])
                elif key == "RandyRainInhibit":
                    if "true" in str(items[1]).lower():
                        allSettings.randy.rainInhibit = float(items[2])
                elif key == "RandyWindInhibit":
                    if "true" in str(items[1]).lower():
                        allSettings.randy.windInhibit = float(items[2])
                elif key == "RandySprinklerInhibit":
                    allSettings.randy.sprinklerInhibit = bool(items[1])
                elif key == "SprinklerNorth":
                    if "true" in str(items[1]).lower():
                        allSettings.sprinkler.north = ControlFileReader.__hhmmssToTimedelta(items[2])
                elif key == "SprinklerWest":
                    if "true" in str(items[1]).lower():
                        allSettings.sprinkler.west = ControlFileReader.__hhmmssToTimedelta(items[2])
                elif key == "SprinklerEast":
                    if "true" in str(items[1]).lower():
                        allSettings.sprinkler.east = ControlFileReader.__hhmmssToTimedelta(items[2])
                elif key == "SprinklerSchedule":
                    schedule = dt.datetime.strptime(items[1] + " " + items[2], "%Y-%m-%d %H:%M:%S")
                    allSettings.sprinkler.schedules.append(schedule)
                elif key == "SprinklerWindInhibit":
                    if "true" in str(items[1]).lower():
                        allSettings.sprinkler.windInhibit = float(items[2])
                elif key == "WeatherOwm":
                    if "true" in str(items[1]).lower():
                        allSettings.weatherOwm = dt.datetime.strptime(items[2], '%H:%M:%S').time()
                elif key == "LocalSensors":
                    if "true" in str(items[1]).lower():
                        for i in range(2, len(items)):
                            allSettings.localSensors.append(dt.datetime.strptime(items[i], '%H:%M:%S').time())
                else:
                    logger.warning("ControlFileReader.__read(): Unrecognized line in " + 
                                   CONTROL_FILENAME + ": " + line.strip())
            
        file.close()
        return allSettings
    

    # puts randy charge jobs to the jobQueue        
    @staticmethod    
    def put_new_randy_charge_jobs(jobQueue, allSettings=None):
        if allSettings is None:
            allSettings = ControlFileReader.__read()

        now = dt.datetime.now().time()
        if allSettings.randy.chargeOn == allSettings.randy.chargeOff:
            logger.warning("ControlFileReader.put_all_new_jobs(): No charging because randy.chargeOn = randy.chargeOff!")
        elif allSettings.randy.chargeOff < allSettings.randy.chargeOn:  # means charging is on over midnight
            if now <= allSettings.randy.chargeOff:     # should be charging right now
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.chargeOff, ("charge", False)))
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.chargeOn, ("charge", True)))
            elif now <= allSettings.randy.chargeOn:    # should be not charging right now
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.chargeOn, ("charge", True)))
        else:         # means charging is off over midnight
            if now <= allSettings.randy.chargeOn:     
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.chargeOn, ("charge", True)))
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.chargeOff, ("charge", False)))
            elif now <= allSettings.randy.chargeOff:    
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.chargeOff, ("charge", False)))


    # puts randy mow jobs to the jobQueue        
    @staticmethod    
    def put_new_randy_mow_jobs(jobQueue, allSettings=None):
        if allSettings is None:
            allSettings = ControlFileReader.__read()

        now = dt.datetime.now().time()
        if allSettings.randy.mowOn == allSettings.randy.mowOff:
            logger.warning("ControlFileReader.put_all_new_jobs(): No mowing because randy.mowOn = randy.mowOff!")
        elif allSettings.randy.mowOff < allSettings.randy.mowOn:  # means charging is on over midnight
            logger.warning("ControlFileReader.put_all_new_jobs(): No mowing because no mowing over midnight is possible!")
        else:
            if now <= allSettings.randy.mowOn:     
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.mowOn, ("mow", True)))
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.mowOff, ("mow", False)))
            elif now <= allSettings.randy.mowOff:    
                jobQueue.put(Job.gen_randy_switch_job(allSettings.randy.mowOff, ("mow", False)))
    

    # puts sprinkler jobs to the jobQueue        
    # input buttonNow <bool> is True if sprinklers are started from button (not schedules)
    @staticmethod    
    def put_new_sprinkler_jobs(jobQueue, allSettings=None, buttonNow=False):
        if allSettings is None:
            allSettings = ControlFileReader.__read()

        now = dt.datetime.now()
        tomorrow = now.date() + dt.timedelta(1)
        nextInit = dt.datetime.combine(tomorrow, TIME_DAILY_INIT)
        
        if buttonNow:  # function called from button press
            schedules = [now + SPRINKLER_PAUSE]
        else:          # function called from load control.txt
            schedules = allSettings.sprinkler.schedules

        for t in schedules:
            if t > now and t < nextInit:
                jobs = []
                if bool(allSettings.sprinkler.north):   # sprinkler north is enabled 
                    jobs.append(Job(t, JKey.SWITCH_SPRINKLER, (1,0,0)))
                    t += allSettings.sprinkler.north
                    jobs.append(Job(t, JKey.SWITCH_SPRINKLER, (0,0,0)))
                    t += SPRINKLER_PAUSE
                if bool(allSettings.sprinkler.west):   # sprinkler west is enabled 
                    jobs.append(Job(t, JKey.SWITCH_SPRINKLER, (0,1,0)))
                    t += allSettings.sprinkler.west
                    jobs.append(Job(t, JKey.SWITCH_SPRINKLER, (0,0,0)))
                    t += SPRINKLER_PAUSE
                if bool(allSettings.sprinkler.east):   # sprinkler east is enabled 
                    jobs.append(Job(t, JKey.SWITCH_SPRINKLER, (0,0,1)))
                    t += allSettings.sprinkler.east
                    jobs.append(Job(t, JKey.SWITCH_SPRINKLER, (0,0,0)))
                    t += SPRINKLER_PAUSE
                
                # check if start date equals stop date
                # sprinkler over midnight would interfer with daily init
                if len(jobs) > 0:
                    if min(jobs).t.date() == max(jobs).t.date(): 
                        for job in jobs:
                            jobQueue.put(job)
                    else:
                        logger.warning("ControlFileReader.put_all_new_jobs(): Sprinkler schedule over midnight filtered out.")
                            

    # reads control.txt file and puts new jobs to a job-queue
    @staticmethod    
    def put_all_new_jobs(jobQueue):
        allSettings = ControlFileReader.__read()
        
        # (1) generate randy charge jobs
        ControlFileReader.put_new_randy_charge_jobs(jobQueue, allSettings)
        
        # (2) generate randy mow jobs
        ControlFileReader.put_new_randy_mow_jobs(jobQueue, allSettings)        

        # (3) generate spinkler jobs
        ControlFileReader.put_new_sprinkler_jobs(jobQueue, allSettings)
        
        # (4) generate weather OWM jobs
        if bool(allSettings.weatherOwm):
            if dt.datetime.now().time() < allSettings.weatherOwm:  # weather OWM aquisition in the future?
                jobQueue.put(Job.gen_weather_owm_job(allSettings.weatherOwm))


### Test bench #### 
if __name__ == "__main__":
    print("Testing garden_jobs.py ...")

    # constants
    PERIOD_BUTTON_SCAN_ASLEEP = dt.timedelta(0,5)       # Period of scanning the buttons in State.ASLEEP
    PERIOD_BUTTON_SCAN_AWAKE = dt.timedelta(0,0,50000)  # Period of scanning the buttons in State.AWAKE
    SHORT_BUTTON_PRESS = dt.timedelta(0,0,500000)   # After this time (from releasing the button) the ButtonEvent (single, double, tripple) is emitted
    LONG_BUTTON_PRESS = dt.timedelta(0,1,200000)   # After this time a button press is recognized as long button presss
    PWDN_TIMEOUT = dt.timedelta(0,4,0)      # How to keep back-button pressed in State.ABOUT_TO_PWDN before it actually powers down
    INACT_TIMEOUT = dt.timedelta(0,20,500000)    # Return to next lower state after this time of button inactivity

    # inits
    mainState = MainStateMashine(SHORT_BUTTON_PRESS, LONG_BUTTON_PRESS, PWDN_TIMEOUT, 
                                 INACT_TIMEOUT)

    jobQueue = JobQueue()
    jobQueue.put(Job.gen_daily_init_job(TIME_DAILY_INIT))
    jobQueue.put(Job.gen_button_scan_job(mainState.state, PERIOD_BUTTON_SCAN_ASLEEP, PERIOD_BUTTON_SCAN_AWAKE))  
    
    
    print(jobQueue)
    print("\n")
    ControlFileReader.put_all_new_jobs(jobQueue)
    
    print(jobQueue)
    

    
    