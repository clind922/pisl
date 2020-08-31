#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

import requests
import datetime
import time
import os
import math

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

data_refresh_delay_normal = 120 # Normal API frefresh fequency
data_refresh_delay_fast = 30 # A faster API refresh freqency

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

last_get_deps = None
button_press_time = None
departures = None

REALTIME_API_KEY = os.getenv("REALTIME_API_KEY")

PREFERRED_JOURNEY_DIRECTION = os.getenv("PREFERRED_JOURNEY_DIRECTION") # SL API direction to draw fully
PREFERRED_JOURNEY_DIRECTION = int(PREFERRED_JOURNEY_DIRECTION)

TRANSPORT_TYPE = os.getenv("TRANSPORT_TYPE")

SL_SITE_ID = os.getenv("SL_SITE_ID")
#Sätra = 9288
#Liljeholmen = 9294

ACTIVE_HOURS = os.getenv("ACTIVE_HOURS")

def button_callback(channel):
    global button_press_time
    # Set button press time
    button_press_time = datetime.datetime.now()
    # Force API refresh
    last_get_deps = None
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

def get_departures():
    print('Making API call...')
    
    url = "http://api.sl.se/api2/realtimedeparturesV4.json?key=%s&siteid=%s&timewindow=30" % (REALTIME_API_KEY, SL_SITE_ID)
    resp = requests.get(url)

    if resp.status_code != 200:
        # This means something went wrong.
        raise ApiException('HTTP return code is not 200: {}'.format(resp.status_code))
    json = resp.json()

    if(json['StatusCode'] != 0):
        raise ApiException('Status code is not 0: {}'.format(json['StatusCode']))

    data = json['ResponseData']
    transport_type = data[TRANSPORT_TYPE]
    departures = {1: [], 2: [], 0: []}
    for item in transport_type:
        departures[item['JourneyDirection']].append(item)

    return departures

def draw_deps(draw, data_refresh_delay):
    global row
    global last_get_deps
    global departures
    if departures is None or time_diff(last_get_deps) > data_refresh_delay:
        try:
            departures = get_departures()
        except ApiException as e:
            print_out (str(e), '', draw=draw)
            time.sleep(data_refresh_delay_fast) # 30s
            return
        except (ConnectionError, ConnectTimeout, HTTPError, ReadTimeout, Timeout) as e:
            print_out (str(e), '', draw=draw)
            time.sleep(data_refresh_delay_fast) # 30s
            return
        except ValueError as e: # Can be internet connection failure
            print_out (str(e), '', draw=draw)
            time.sleep(data_refresh_delay_fast * 10) # 5m
            return 
        last_get_deps = datetime.datetime.now()
    
    print_buffer = {}
    deviations_shown = []
    preferred_num_printed = 0

    for di, deps in departures.items():
        if di == 0:
            continue

        for dep in deps:
            diff = time_diff(dep['ExpectedDateTime'], absVal=False)
            if diff < 0:
                continue
            est_min = int(math.floor(diff / 60))
            if est_min == 0:
                est_min = 'Nu'
            else:
                est_min = '{} min'.format(est_min)
            # Print full list, if it is the preferred dir
            if di == PREFERRED_JOURNEY_DIRECTION:
                # Only print 3
                if preferred_num_printed == 3:
                    continue
                print_out(u'{} {}'.format(dep['LineNumber'], dep['Destination']), '{}'.format(est_min), draw=draw)
                preferred_num_printed += 1

            else:
                key = u''.join(dep['LineNumber'] + ' ' + dep['Destination'])
                if key not in print_buffer:
                    print_buffer[key] = []
                print_buffer[key].append(dep)

            # Look for deviations and collect them
            if dep['Deviations'] is not None:
                for deviation in dep['Deviations']:
                    if deviation['ImportanceLevel'] > 3:
                        deviations_shown.append(deviation['Consequence'] + ' ' + deviation['Text'])
    # Print deviations
    if deviations_shown:
        print_out(u'{}'.format(', '.join(deviations_shown)), draw=draw)
    else:
        print_out('', 'Data age: {}s'.format(time_diff(last_get_deps)), draw=draw)

    # Empty the print buffer for printing low prio deps last
    if print_buffer:

        if row + len(print_buffer) < max_rows:
            row += (max_rows - row - len(print_buffer))
        for dest, deps in print_buffer.items():
            temp = []
            for dep in deps:
                diff = time_diff(dep['ExpectedDateTime'], absVal=False)
                if diff < 0:
                    continue
                est_min = int(math.floor(diff / 60))
                if est_min == 0:
                    est_min = 'Nu'
                else:
                    est_min = '{}m'.format(est_min)
                #temp.append('{} [{}]'.format(dep['DisplayTime'], est_min))
                temp.append(est_min)
                if len(temp) == 2:
                    break

            print_out(u'{}'.format(dest), '{}'.format(','.join(temp)), draw=draw)
            if row == max_rows:
                break
    row = 0

def main():

    while True:
        with canvas(device) as draw:
            # Only draw if started recently
            if time_diff(start_time) < screen_active_time:
                draw_deps(draw, data_refresh_delay_normal)
            # Or only draw if active hours
            elif ACTIVE_HOURS is not None and is_active_hours(ACTIVE_HOURS, screen_active_time):
                draw_deps(draw, data_refresh_delay_normal)
            # Or if button is pressed recently
            elif button_press_time is not None and time_diff(button_press_time) < screen_active_time:
                draw_deps(draw, data_refresh_delay_fast)
        time.sleep(screen_data_refresh_delay)

if __name__ == "__main__":
    if SL_SITE_ID is None:
        exit("SL_SITE_ID env missing.")
    if REALTIME_API_KEY is None:
        exit("REALTIME_API_KEY env missing.")
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
