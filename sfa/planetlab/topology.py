##
# SFA Topology Info
#
# This module holds topology configuration for SFA. It is implemnted as a 
# list of site_id tuples

import os.path
import traceback
from sfa.util.sfalogging import logger

class Topology(set):
    """
    Parse the topology configuration file. 
    """

    def __init__(self, config_file = "/etc/sfa/topology"):
        set.__init__(self) 
        try:
            # load the links
            f = open(config_file, 'r')
            for line in f:
                ignore = line.find('#')
                if ignore > -1:
                    line = line[0:ignore]
                tup = line.split()
                if len(tup) > 1:
                    self.add((tup[0], tup[1]))    
        except Exception, e:
            logger.log_exc("Could not find or load the configuration file: %s" % config_file)
            raise
