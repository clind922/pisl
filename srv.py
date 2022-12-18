#!/-usr/bin/env python
# -*- coding: utf-8 -*-
#

import requests
import datetime
import time
import os
import math
import re
import sys, traceback

from helpers import make_font
from helpers import time_diff
from helpers import tdiff
from helpers import tdiff_text
from helpers import is_active_hours
from helpers import print_log
from helpers import ApiException
from requests import ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError
from urllib3.exceptions import NewConnectionError

from oled_options import get_device
from luma.core.render import canvas
from PIL import ImageFont
from dateutil.parser import parse
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library

from dotenv import load_dotenv

load_dotenv(dotenv_path='.env', encoding='utf8')

data_refresh_delay_normal = 3600*12 # Normal API frefresh fequency
data_refresh_delay_fast = 3600*4 # A faster API refresh freqency

screen_data_refresh_delay = 1 # Redraw (cached) data every X seconds
screen_data_refresh_delay_flash = 1
screen_active_time = 120 # In seconds, how long the screen is active after button press (during off-hours)

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
screen_flash = True
screen_flash_test = False
debug_count = 0

SRV_STREETNAME = os.getenv("SRV_STREETNAME")
SRV_CITY = os.getenv("SRV_CITY")

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

def print_out(left_text='', right_text='', draw=None):
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
        draw.text((0, y), left_text + ' ' + right_text, font=font, fill="white")

def get_srv_date(iso_date):
    p = re.compile(r'(?P<year>.+)-(?P<month>\d+)-(?P<day>.+)')
    m = p.search(iso_date);
    day = int(m.group('day'))
    month = int(m.group('month'))
    year = int(m.group('year'))
   
    return datetime.datetime(year, month, day, 9, 0, 0)

def get_services():
    print_log('Making API call...')
    
    url = "https://www.srvatervinning.se/rest-api/srv-slamsok-rest-new/search?query=%s&city=%s" % (SRV_STREETNAME, SRV_CITY)
    resp = requests.get(url)

    if resp.status_code != 200:
        raise ApiException('HTTP return code is not 200: {}'.format(resp.status_code))
    json = resp.json()
    
    services = {}
    now = time.mktime(time.localtime())
    
    for result in json['results']:

        for container in result['containers']:
            for date in container['calendars']:
                dt = get_srv_date(date['startDate'])
                ts = time.mktime(dt.timetuple())
                if ts >= now:
                    dfmt = '%-d/%-m'
                    dfmt = dt.strftime(dfmt.replace('%-', '%#') if os.name == 'nt' else dfmt)
                    next_text = u'{} {}{} {}'.format(container['containerType'].replace(u'Kärl 370 liter fyrfack kärl', 'K'), dfmt, ' ' * (5 - len(dfmt)), tdiff_text(ts, True, 2, True).replace(' ', ''))
                    services[ts] = next_text
    return services

def draw_srv(draw, data_refresh_delay):
    global row
    global last_get_services
    global srv_services
    global screen_flash
    global debug_count
    if srv_services is None or time_diff(last_get_services) > data_refresh_delay:
        try:
            srv_services = get_services()
        except ApiException as e:
            print_out(str(e), '', draw=draw)
            print_log('E1')
            print_log(str(e))
            time.sleep(30)
            return
        except (ConnectionError, ConnectTimeout, HTTPError, ReadTimeout, Timeout, NewConnectionError) as e:
            print_out(str(e), '', draw=draw)
            print_log('E2')
            print_log(str(e))
            print_log('-'*60)
            print_log(traceback.format_exc())
            print_log('-'*60)
            time.sleep(300) # 5m
            print_log('-DEBUG-')
            time.sleep(100)
            print_log('-DEBUG_2-')
            debug_count = debug_count + 1  
            print_log(debug_count)
            return
        except ValueError as e: # Can be internet connection failure
            print_out(str(e), '', draw=draw)
            print_log('E3')
            print_log(str(e))
            time.sleep(60 * 5) # 5m
            return
        last_get_services = datetime.datetime.now()
        if len(srv_services) == 0:
            print_log('Empty result')
            time.sleep(60 * 5) # 5m
            return

    for key in sorted(srv_services):
        if screen_flash and (tdiff(int(key), False) < 3600*24 or screen_flash_test):
            time.sleep(screen_data_refresh_delay_flash)
            screen_flash = False
            return
        break

    for key in sorted(srv_services):
        if(row < max_rows):
            print_out(srv_services[key], draw=draw)

    screen_flash = True
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
