from types import StringTypes
import dateutil.parser
import datetime

from sfa.util.sfalogging import logger

def utcparse(input):
    """ Translate a string into a time using dateutil.parser.parse but make sure it's in UTC time and strip
the timezone, so that it's compatible with normal datetime.datetime objects.

For safety this can also handle inputs that are either timestamps, or datetimes
"""
    
    if isinstance (input, datetime.datetime):
        logger.warn ("argument to utcparse already a datetime - doing nothing")
        return input
    elif isinstance (input, StringTypes):
        t = dateutil.parser.parse(input)
        if t.utcoffset() is not None:
            t = t.utcoffset() + t.replace(tzinfo=None)
        return t
    elif isinstance (input, (int,float)):
        return datetime.datetime.fromtimestamp(input)
    else:
        logger.error("Unexpected type in utcparse [%s]"%type(input))

