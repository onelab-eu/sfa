#----------------------------------------------------------------------
# Copyright (c) 2008 Board of Trustees, Princeton University
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------
from types import StringTypes
import time
import datetime
import dateutil.parser
import calendar
import re

from sfa.util.sfalogging import logger

SFATIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def utcparse(input):
    """ Translate a string into a time using dateutil.parser.parse but make sure it's in UTC time and strip
the timezone, so that it's compatible with normal datetime.datetime objects.

For safety this can also handle inputs that are either timestamps, or datetimes
"""

    def handle_shorthands (input):
        """recognize string like +5d or +3w or +2m as 
        2 days, 3 weeks or 2 months from now"""
        if input.startswith('+'):
            match=re.match (r"([0-9]+)([dwm])",input[1:])
            if match:
                how_many=int(match.group(1))
                what=match.group(2)
                if what == 'd':         d=datetime.timedelta(days=how_many)
                elif what == 'w':       d=datetime.timedelta(weeks=how_many)
                elif what == 'm':       d=datetime.timedelta(weeks=4*how_many)
                return datetime.datetime.utcnow()+d

    # prepare the input for the checks below by
    # casting strings ('1327098335') to ints
    if isinstance(input, StringTypes):
        try:
            input = int(input)
        except ValueError:
            try:
                new_input=handle_shorthands(input)
                if new_input is not None: input=new_input
            except:
                import traceback
                traceback.print_exc()

    #################### here we go
    if isinstance (input, datetime.datetime):
        #logger.info ("argument to utcparse already a datetime - doing nothing")
        return input
    elif isinstance (input, StringTypes):
        t = dateutil.parser.parse(input)
        if t.utcoffset() is not None:
            t = t.utcoffset() + t.replace(tzinfo=None)
        return t
    elif isinstance (input, (int,float,long)):
        return datetime.datetime.fromtimestamp(input)
    else:
        logger.error("Unexpected type in utcparse [%s]"%type(input))

def datetime_to_string(dt):
    return datetime.datetime.strftime(dt, SFATIME_FORMAT)

def datetime_to_utc(dt):
    return time.gmtime(datetime_to_epoch(dt))

# see https://docs.python.org/2/library/time.html 
# all timestamps are in UTC so time.mktime() would be *wrong*
def datetime_to_epoch(dt):
    return int(calendar.timegm(dt.timetuple()))

def add_datetime(input, days=0, hours=0, minutes=0, seconds=0):
    """
    Adjust the input date by the specified delta (in seconds).
    """
    dt = utcparse(input)
    return dt + datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

if __name__ == '__main__':
        # checking consistency
    print 20*'X'
    print ("Should be close to zero: %s"%(datetime_to_epoch(datetime.datetime.utcnow())-time.time()))
    print 20*'X'
    for input in [
            '+2d',
            '+3w',
            '+2m',
            1401282977.575632,
            1401282977,
            '1401282977',
            '2014-05-28',
            '2014-05-28T15:18',
            '2014-05-28T15:18:30',
    ]:
        print "input=%20s -> parsed %s"%(input,datetime_to_string(utcparse(input)))
