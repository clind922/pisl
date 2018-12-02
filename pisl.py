#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

import requests
import datetime
import time
import os
import math
from dateutil.parser import parse
from helpers import make_font, time_diff, ApiException

from oled_options import get_device
from luma.core.virtual import terminal
from PIL import ImageFont

realtime_api_key = "75373d23fb0a4c47b7f3625c6fe97199"
site_id = "9294"
#Sätra = 9288
#Liljeholmen = 9294
preferred_dir = 1
refresh_freq = 120 #s

screen_refresh_freq = 5 #s

size = 15 # Font size
term = None

def print_out(left_text='', right_text='', term=None):
    if term is None:
        print('StdOut: ' + left_text + ' ' + right_text)
    else:
        l_len = len(left_text)
        r_len = len(right_text)
        if l_len + r_len >= term.width:
            left_text = left_text[:(term.width - r_len)]
        else:
            right_text = ' ' * (term.width - l_len - r_len) + right_text
        term.puts(left_text + right_text + '\n')

def get_departures():

    print_out('Making API call...', term=term)
    
    url = "http://api.sl.se/api2/realtimedeparturesV4.json?key=%s&siteid=%s&timewindow=30" % (realtime_api_key, site_id)

    resp = requests.get(url)

    if resp.status_code != 200:
        # This means something went wrong.
        raise ApiException('HTTP return code is not 200: {}'.format(resp.status_code))

    json = resp.json()

    if(json['StatusCode'] != 0):
        raise ApiException('Status code is not 0: {}'.format(json['StatusCode']))

    data = json['ResponseData']

    metros = data['Metros']

    departures = {1: [], 2: [], 0: []}

    for item in metros:
        departures[item['JourneyDirection']].append(item)

    return departures

def main():
    font = make_font("ProggyTiny.ttf", size)
    term = terminal(device, font)
    term.animate = False
    last_get_deps = None
    departures = None
    while True:
        term.clear()
        if departures is None or time_diff(last_get_deps) > refresh_freq:

            try:
                departures = get_departures()
            except ApiException as e:
                print_out (e, term=term)
                term.flush()
                time.sleep(screen_refresh_freq * 2)
                continue
            last_get_deps = datetime.datetime.now()

        print_out('Age: {}s'.format(time_diff(last_get_deps)), term=term)
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
                est_min = int(math.floor(diff/60))
                if est_min == 0:
                    est_min = 'Nu'
                else:
                    est_min = '{} min'.format(est_min)
                # Print full list, if it is the preferred dir
                if di == preferred_dir:
                    # Only print 3
                    if preferred_num_printed == 3:
                        continue
                    print_out(u'{} {}'.format(dep['LineNumber'], dep['Destination']), '{}'.format(est_min), term=term)
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
            print_out(u'{}'.format(', '.join(deviations_shown)), term=term)
        #else:
        #    print_out('', term=term)

        # Empty the print buffer for printing low prio deps last
        if print_buffer:
            for dest, deps in print_buffer.items():
                temp = []
                for dep in deps:
                    #print_out(dep, term=term)
                    diff = time_diff(dep['ExpectedDateTime'], absVal=False)
                    if diff < 0:
                        continue
                    est_min = int(math.floor(diff/60))
                    if est_min == 0:
                        est_min = 'Nu'
                    else:
                        est_min = '{}m'.format(est_min)
                    #temp.append('{} [{}]'.format(dep['DisplayTime'], est_min))
                    temp.append(est_min)
                    break # temp only 1

                print_out(u'{}'.format(dest), '{}'.format(','.join(temp)), term=term)
                break # temp only 1
        time.sleep(screen_refresh_freq)
    term.flush()

if __name__ == "__main__":
    try:
        device = get_device()
        main()
    except KeyboardInterrupt:
        pass
