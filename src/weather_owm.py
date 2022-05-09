# -*- coding: utf-8 -*-
"""
Created on Sun May 12 11:18:56 2019

@author: holge
"""

from time import sleep
import requests
from collections import OrderedDict
import datetime as dt
import numpy as np


OWM_URL = "http://api.openweathermap.org/data/2.5/___&units=metric"
OWM_KEY = "bbb8b6ef0bb6dc86523bb6957f17b70f"
NYMPFENBURG = "lat=48.182774&lon=11.500496"
REQUEST_TRIALS = 0
REQUEST_PAUSE = 60
NUM_DIGITS = 4


class WeatherDailyAvg(OrderedDict):
    def __init__(self, date):
        super().__init__(self)
        self["date"] = date
        self["time"] = []
        self["T [°C]"] = []
        self["rain [mm/h]"] = []
        self["snow [mm/h]"] = []
        self["pressure [hPa]"] = [] 
        self["humidity [%]"] = []            
        self["clouds [%]"] = []            
        self["wind [m/s]"] = []            
        
    
    def __str__(self):
        s = str(self["date"])
        for key, val in self.items():
            if type(val) == list:
                s += "\n\t{} = {}".format(key, val)
        return s
    
    
    # returns <OrderedDict> of averages
    def get_means(self):
        ret = OrderedDict()
        for key, val in self.items():
            if type(val) == list:
                if len(val) == 0:
                    ret[key] = 0.
                else:
                    ret[key] = np.round(np.array(val).mean(), decimals=NUM_DIGITS)
        return ret



class WeatherForecast(list):
    # input <dict> wd = weather data from owm json
    # input <int> nDays = number of days to forecast (max=5)
    def __init__(self, wd, nDays=3):
        super().__init__(self)

        # construct a WeatherDailyAvg obj for each day in the forecast
        for day in range(nDays+1):
            date = (dt.datetime.today() + dt.timedelta(day)).date()
            self.append(WeatherDailyAvg(date))
        
        for meas in wd["list"]:
            timestamp = dt.datetime.fromtimestamp(meas["dt"])
            day = (timestamp.date() - dt.datetime.today().date()).days
            if day <= nDays:
                # time of measurement
                self[day]["time"].append(str(timestamp.time()))
                
                # extract temp data
                self[day]["T [°C]"].append(np.round(meas["main"]["temp"], decimals=NUM_DIGITS))
                
                # extract rain data
                if "rain" in meas.keys():
                    if len(meas["rain"]) > 0:
                        key = next(iter(meas["rain"]))
                        hours = int(key.strip("h"))
                        rain = np.round(meas["rain"][key] / hours, decimals=NUM_DIGITS)
                        self[day]["rain [mm/h]"].append(rain)
                    else:
                        self[day]["rain [mm/h]"].append(0)
                else:
                    self[day]["rain [mm/h]"].append(0)
                    
                # extract snow data
                if "snow" in meas.keys():
                    if len(meas["snow"]) > 0:
                        key = next(iter(meas["snow"]))
                        hours = int(key.strip("h"))
                        snow = np.round(meas["snow"][key] / hours, decimals=NUM_DIGITS)
                        self[day]["snow [mm/h]"].append(snow)
                    else:
                        self[day]["snow [mm/h]"].append(0)
                else:
                    self[day]["snow [mm/h]"].append(0)
            
                # extract humidity data
                self[day]["humidity [%]"].append(np.round(
                        meas["main"]["humidity"], decimals=NUM_DIGITS))
                
                # extract pressure data
                self[day]["pressure [hPa]"].append(np.round(
                        meas["main"]["pressure"], decimals=NUM_DIGITS))
                
                # extract clouds data
                if "clouds" in meas.keys():
                    self[day]["clouds [%]"].append(np.round(
                            meas["clouds"]["all"], decimals=NUM_DIGITS))
                else:
                    self[day]["clouds [%]"].append(0)
                
                # extract wind data
                if "wind" in meas.keys():
                    self[day]["wind [m/s]"].append(np.round(
                            meas["wind"]["speed"], decimals=NUM_DIGITS))
                else:
                    self[day]["wind [m/s]"].append(0)
                    
    
    def __str__(self):
        s = ""
        for day, wd in enumerate(self):
            s += "WeatherForecast +{} days:\n{}".format(day, wd)
        return s
        

    # return the avg rain [mm/h] for that date during daytime hours (btw begin and end)
    # input date: datetime.date()
    def get_rain_at_daytime(self, date, begin=dt.time(8,0,0), end=dt.time(18,0,0)):
        for wd in self:
            if wd["date"] == date:
                rainAtDaytime = list()
                for timeStr, rain in zip(wd["time"], wd["rain [mm/h]"]):
                    time = dt.datetime.strptime(timeStr, '%H:%M:%S').time()
                    if time >= begin and time <= end:
                        rainAtDaytime.append(rain)
                if len(rainAtDaytime) > 0:
                    return np.array(rainAtDaytime).mean()
                else: 
                    return None  # if there is no rain data between "begin" and "end"
        return None  # if no weather forcast is available for the requested date
            
                
class WeatherContainer(OrderedDict):
    # input <dict> wd = weather data from owm json
    def __init__(self, wd):
        super().__init__(self)
        self["T [°C]"] = wd["main"]["temp"]            
        
        # extract wind rain
        if "rain" in wd.keys():
            key = next(iter(wd["rain"]))
            hours = int(key.strip("h"))
            self["rain [mm/h]"] = np.round(wd["rain"][key] / hours, decimals=NUM_DIGITS)
        else:
            self["rain [mm/h]"] = 0
            
        # extract wind data
        if "wind" in wd.keys():
            self["wind [m/s]"] = np.round(wd["wind"]["speed"], decimals=NUM_DIGITS)
        else:
            self["wind [m/s]"] = 0

        #self["Tmin [°C]"] = wd["main"]["temp_min"]            
        #self["Tmax [°C]"] = wd["main"]["temp_max"]            
        #self["pressure [hPa]"] = wd["main"]["pressure"]            
        #self["dt"] = dt.datetime.fromtimestamp(wd["dt"])
        #self["dscr"] = wd["weather"][0]["description"]
        #self["visibility"] = wd["visibility"]            
        #self["wind dir [°]"] = wd["wind"]["deg"]            
        #self["sunrise"] = dt.datetime.fromtimestamp(wd["sys"]["sunrise"]).time()
        #self["sunset"] = dt.datetime.fromtimestamp(wd["sys"]["sunset"]).time()
        

    def __str__(self):
        s = ""
        for key, val in self.items():
            s += "{} = {}\n".format(key, val)
        return s


# returns <tuple> (success, requestTrials, WeatherContainer)
def get_weather_forcast():
    url = OWM_URL.replace("___", "forecast?{}&appid={}".format(NYMPFENBURG, OWM_KEY))
    requestTrials = 0
    while True:
        try:
            wd = requests.get(url).json()
            wf = WeatherForecast(wd, nDays=3)            
            return (True, requestTrials, wf)
        except Exception as e:
            print("Exception during weather request {}/{}:\n{}".format(
                    requestTrials + 1, REQUEST_TRIALS, e))
            if requestTrials >= REQUEST_TRIALS:
                return (False, requestTrials, None)
            else:
                requestTrials += 1
                sleep(REQUEST_PAUSE)


# returns <tuple> (success, requestTrials, WeatherContainer)
def get_current_weather():
    url = OWM_URL.replace("___", "weather?{}&appid={}".format(NYMPFENBURG, OWM_KEY))
    requestTrials = 0
    while True:
        try:
            wd = requests.get(url).json()
            wc = WeatherContainer(wd)
            return (True, requestTrials, wc)
        except Exception as e:
            print("Exception during weather request {}/{}:\n{}".format(
                    requestTrials + 1, REQUEST_TRIALS, e))
            if requestTrials >= REQUEST_TRIALS:
                return (False, requestTrials, None)
            else:
                requestTrials += 1
                sleep(REQUEST_PAUSE)
            
            
            
if __name__ == "__main__":
    success, trials, wf = get_weather_forcast()
    print(50*"+")
    print(wf)
    success, trials, cw = get_current_weather()
    print(50*"+")
    print(cw)


