#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2014-18 Richard Hull and contributors
# See LICENSE.rst for details.

from PIL import ImageFont

import os.path
import datetime
import time
import croniter

import math

def make_font(name, size):
    font_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 'fonts', name))
    return ImageFont.truetype(font_path, size)

def time_diff(dt, absVal=True):
    if type(dt) != datetime.datetime:
        dt = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    t1 = time.mktime(dt.timetuple())
    now = time.mktime(time.localtime())
    diff = t1 - now
    if absVal:
        diff = abs(diff)
    return int(diff)
def tdiff(ts, absVal=True):
    now = time.mktime(time.localtime())
    diff = ts - now
    if absVal:
        diff = abs(diff)
    return int(diff)

def tdiff_text(ts, absVal=True, max_precision=6):
    out = []
    diff = tdiff(ts, absVal)
    for unit, suffix_plural, suffix in ((3600*24*30*365, 'år', 'år'), (3600*24*30, 'månader', 'månad'), (3600*24, 'dagar', 'dag'), (3600, 'timmar', 'timme'), (60, 'minuter', 'minut'), (1, 'sekunder', 'sekund')):
        if diff >= unit:
            val = int(math.floor(diff / unit))
            if val != 1:
                suffix = suffix_plural
            out.append('{} {}'.format(val, suffix))
            diff -= val * unit
            max_precision -= 1
            if max_precision == 0:
                break
    if len(out) > 1:
        out[len(out) - 1] = ' och ' + out[len(out) - 1]
    return ', '.join(out)

def is_active_hours(active_hours, limit):
    now = datetime.datetime.now()
    cron = croniter.croniter(active_hours, now)
    next_d = cron.get_next(datetime.datetime)
    diff = time_diff(next_d)
    return diff < 120

class ApiException(Exception):
	pass
