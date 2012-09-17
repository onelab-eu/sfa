import sys
import xmlrpclib
import socket
from urlparse import urlparse

from sfa.util.sfalogging import logger

class NitosShell:
    """
    A simple xmlrpc shell to a NITOS Scheduler instance
    This class can receive all NITOS API  calls to the underlying testbed
    For safety this is limited to a set of hard-coded calls
    """
    
    direct_calls = ['getNodes','getChannels','getSlices','getUsers','getReservedNodes',
                    'getReservedChannels','getTestbedInfo',
                    'reserveNodes','reserveChannels','addSlice','addUser','addUserToSlice',
                    'addUserKey','addNode', 'addChannel',
                    'updateReservedNodes','updateReservedChannels','updateSlice','updateUser',
                    'updateNode', 'updateChannel',
                    'deleteNode','deleteChannel','deleteSlice','deleteUser', 'deleteUserFromSLice',
                    'deleteKey', 'releaseNodes', 'releaseChannels'
                    ]


    # use the 'capability' auth mechanism for higher performance when the PLC db is local    
    def __init__ ( self, config ) :
        url = config.SFA_NITOS_URL
        self.proxy = xmlrpclib.Server(url, verbose = False, allow_none = True)

    def __getattr__(self, name):
        def func(*args, **kwds):
            actual_name=None
            if name in NitosShell.direct_calls: actual_name=name
            if not actual_name:
                raise Exception, "Illegal method call %s for NITOS driver"%(name)
            actual_name = "scheduler.server." + actual_name
            result=getattr(self.proxy, actual_name)(*args, **kwds)
            logger.debug('NitosShell %s (%s) returned ... '%(name,actual_name))
            return result
        return func

