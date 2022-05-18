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

def tdiff_text(ts, absVal=True, max_precision=6, short=False):
    out = []
    diff = tdiff(ts, absVal)
    for unit, suffix_plural, suffix, suffix_short in ((3600*24*30*365, 'år', 'år', 'å'), (3600*24*30, 'månader', 'månad', 'm'), (3600*24*7, 'veckor', 'vecka', 'v'), (3600*24, 'dagar', 'dag', 'd'), (3600, 'timmar', 'timme', 't'), (60, 'minuter', 'minut', 'm'), (1, 'sekunder', 'sekund', 's')):
        if diff >= unit:
            val = int(math.floor(diff / unit))

            if short:
                suffix = suffix_short
            else:
                if val != 1:
                    suffix = suffix_plural
            out.append('{}{}{}'.format(val, '' if short else ' ',suffix))
            diff -= val * unit
            max_precision -= 1
            if max_precision == 0:
                break
    if len(out) > 1 and short is False:
        out[len(out) - 1] = 'och ' + out[len(out) - 1]
    return ', '.join(out).replace(', och', ' och')

def is_active_hours(active_hours, limit):
    now = datetime.datetime.now()
    cron = croniter.croniter(active_hours, now)
    next_d = cron.get_next(datetime.datetime)
    diff = time_diff(next_d)
    return diff < 120

class ApiException(Exception):
	pass
