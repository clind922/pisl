#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

import requests
import datetime
import time
import os
import math
import re

from helpers import make_font
from helpers import time_diff
from helpers import is_active_hours
from helpers import ApiException
from requests import ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError

from oled_options import get_device
from luma.core.render import canvas
from PIL import ImageFont
from dateutil.parser import parse
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library

from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')

data_refresh_delay_normal = 3600*24 # Normal API frefresh fequency
data_refresh_delay_fast = 3600*4 # A faster API refresh freqency

screen_data_refresh_delay = 5 # Redraw (cached) data every X seconds
screen_active_time = 120 # How long the screen is active after button press (during off-hours)

start_time = datetime.datetime.now()

row = 0
max_rows = 0
font_size = 15
width = 0
height = 0
line_height = 0
button_gpio_pin = 15

last_get_services = None
button_press_time = None
srv_services = None

SRV_STREETNAME = os.getenv("SRV_STREETNAME")
SRV_ITEM = os.getenv("SRV_ITEM")

ACTIVE_HOURS = os.getenv("ACTIVE_HOURS")

def button_callback(channel):
    global button_press_time
    # Set button press time
    button_press_time = datetime.datetime.now()
    # Force API refresh
    last_get_services = None
    print("Button was pushed!")

def button_setup():
    GPIO.setwarnings(False) # Ignore warning for now
    GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
    GPIO.setup(button_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin to be an input pin and set initial value to be pulled low (off)
    GPIO.add_event_detect(button_gpio_pin,GPIO.RISING,callback=button_callback) # Setup event on pin rising edge

def print_out(left_text='', right_text='', draw=None, color="white"):
    global row
    if draw is None:
        print('StdOut: ' + left_text + ' ' + right_text)
    else:

        l_len = len(left_text)
        r_len = len(right_text)
        if l_len + r_len >= max_chars:
            left_text = left_text[:(max_chars - r_len - 1)]
        else:
            right_text = ' ' * (max_chars - l_len - r_len - 1) + right_text

        y = row * line_height
        row += 1
        draw.text((0, y), left_text + ' ' + right_text, font=font, fill=color)

def get_srv_date(swe_date):
    week_days = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
    months = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"]
    p = re.compile(r'(?P<weekday>.+) (?P<day>\d+) (?P<month>.+)')
    m = p.search(swe_date);
    #week_days.index(m.group('weekday')) + 1
    day = int(m.group('day'))
    month = months.index(m.group('month')) + 1
    print(month)
    year = datetime.date.today().year
    # Probably next year if month is next year
    if month < datetime.date.today().month:
        year = year + 1

    return datetime.date(year, month, day)

def get_services():
    print('Making API call...')
    
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    url = "https://www.srvatervinning.se/sophamtning/privat/hamtinformation-och-driftstorningar?sv.target=12.d9ec095172e6db9637d4bf6&sv.12.d9ec095172e6db9637d4bf6.route=/item&item=%s&svAjaxReqParam=ajax&streetname=%s" % (SRV_ITEM, SRV_STREETNAME)
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        raise ApiException('HTTP return code is not 200: {}'.format(resp.status_code))
    json = resp.json()
    
    services = {}
    print(json)
    now = time.mktime(time.localtime())
    
    for service in json['services']:
        for date in service['cycleDates']:
            dt = get_srv_date(date['Date'])
            ts = time.mktime(dt.timetuple())
            if ts >= now:
                dfmt = '%-d/%-m'
                next_text = u'{}: {} ({})'.format(service['serviceDescription'].replace('Sortera hemma, fyrfack k', 'K'), dt.strftime(dfmt.replace('%-', '%#') if os.name == 'nt' else dmft), tdiff_text(ts, True, 2, True) )
                services[ts] = next_text
    return services

def draw_srv(draw, data_refresh_delay):
    global row
    global last_get_services
    global srv_services
    if srv_services is None or time_diff(last_get_services) > data_refresh_delay:
        try:
            srv_services = get_services()
        except ApiException as e:
            print_out (str(e), '', draw=draw)
            time.sleep(30)
            return
        except (ConnectionError, ConnectTimeout, HTTPError, ReadTimeout, Timeout) as e:
            print_out (str(e), '', draw=draw)
            time.sleep(30)
            return
        except ValueError as e: # Can be internet connection failure
            print_out (str(e), '', draw=draw)
            time.sleep(30 * 10) # 5m
            return 
        last_get_services = datetime.datetime.now()
    
    print_buffer = {}
    deviations_shown = []
    preferred_num_printed = 0
    
    for key in sorted(services):
        color = "white"
        if tdiff(int(key), Fale) < 3600*24:
            color = "red"
        print_out(services[key], draw=draw, color=color)

    # Reset row
    row = 0

def main():

    while True:
        with canvas(device) as draw:
            # Only draw if started recently
            if time_diff(start_time) < screen_active_time:
                draw_srv(draw, data_refresh_delay_normal)
            # Or only draw if active hours
            elif ACTIVE_HOURS is not None and is_active_hours(ACTIVE_HOURS, screen_active_time):
                draw_srv(draw, data_refresh_delay_normal)
            # Or if button is pressed recently
            elif button_press_time is not None and time_diff(button_press_time) < screen_active_time:
                draw_srv(draw, data_refresh_delay_fast)
        time.sleep(screen_data_refresh_delay)

if __name__ == "__main__":
    if SRV_STREETNAME is None:
        exit("SRV_STREETNAME env missing.")

    try:
        device = get_device()
        width = device.width
        height = device.height
        font = make_font("ProggyTiny.ttf", font_size)
        # Find char width & height
        _cw, _ch = (0, 0)
        for i in range(32, 128):
            w, h = font.getsize(chr(i))
            _cw = max(w, _cw)
            _ch = max(h, _ch)
        max_chars = width // _cw
        line_height = _ch
        max_rows = height // _ch
        start_time = datetime.datetime.now()
        button_setup()
        main()
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup() # Clean up
