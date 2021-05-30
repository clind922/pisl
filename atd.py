#!/usr/bin/env python
# encoding=utf8
# -*- coding: utf-8 -*-
#
# Arbitrary text display
#

import datetime
import time
import os
import io
import math
import re

from helpers import make_font
from helpers import time_diff
from helpers import tdiff_text
from helpers import is_active_hours
from helpers import ApiException

from oled_options import get_device
from luma.core.render import canvas
from PIL import ImageFont
from dateutil.parser import parse
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library

from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')

data_refresh_delay_normal = 30

screen_data_refresh_delay = 1 # Redraw (cached) data every X seconds
screen_active_time = 240 # How long the screen is active after button press (during off-hours)

start_time = datetime.datetime.now()

row = 0
max_rows = 0
font_size = 15
width = 0
height = 0
line_height = 0
button_gpio_pin = 15

button_press_time = None
atd_file_data = None
last_get_deps = None


ACTIVE_HOURS = os.getenv("ACTIVE_HOURS")

def button_callback(channel):
    global button_press_time
    # Set button press time
    button_press_time = datetime.datetime.now()
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

def draw_atd(draw):
    global row
    global last_get_deps
    global atd_file_data
    if atd_file_data is None or last_get_deps is None or time_diff(last_get_deps) > data_refresh_delay:
        f = io.open("atd.txt", "r", encoding="utf-8")
        atd_file_data = f.readlines()
        f.close()
    row = 0

    for line in atd_file_data:
        matches = re.findall("(!([a-z_]+)\((\d+)\))", line)
        for match in matches:
            ret = {}
            exec('val = {}({})'.format(match[1], match[2]), {'tdiff_text': tdiff_text}, ret)
            line = uline.replace(match[0], ret['val'].decode("utf-8"))
        print_out(line, '', draw=draw)
        if row == max_rows:
            break

def main():

    while True:
        with canvas(device) as draw:
            # Only draw if started recently
            if time_diff(start_time) < screen_active_time:
                draw_atd(draw)
            # Or only draw if active hours
            elif ACTIVE_HOURS is not None and is_active_hours(ACTIVE_HOURS, screen_active_time):
                draw_atd(draw)
            # Or if button is pressed recently
            elif button_press_time is not None and time_diff(button_press_time) < screen_active_time:
                draw_atd(draw)
        time.sleep(screen_data_refresh_delay)

if __name__ == "__main__":
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
