#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2014-18 Richard Hull and contributors
# See LICENSE.rst for details.

from PIL import ImageFont

import os.path
import datetime
import time

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

def ApiException(Exception):
	pass
