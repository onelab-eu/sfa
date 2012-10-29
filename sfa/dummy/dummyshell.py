import sys
import xmlrpclib
import socket
from urlparse import urlparse

from sfa.util.sfalogging import logger

class DummyShell:
    """
    A simple xmlrpc shell to the dummy testbed API instance

    """
    
    direct_calls = ['AddNode', 'AddSlice', 'AddUser', 'AddUserKey', 'AddUserToSlice', 'AddSliceToNodes', 
                    'GetTestbedInfo', 'GetNodes', 'GetSlices', 'GetUsers',
                    'DeleteNode', 'DeleteSlice', 'DeleteUser', 'DeleteKey', 'DeleteUserFromSlice', 
                    'DeleteSliceFromNodes',
                    'UpdateNode', 'UpdateSlice', 'UpdateUser',
                   ]


    def __init__ ( self, config ) :
        url = config.SFA_DUMMY_URL
        self.proxy = xmlrpclib.Server(url, verbose = False, allow_none = True)

    def __getattr__(self, name):
        def func(*args, **kwds):
            if not name in DummyShell.direct_calls:
                raise Exception, "Illegal method call %s for DUMMY driver"%(name)
            result=getattr(self.proxy, name)(*args, **kwds)
            logger.debug('DummyShell %s returned ... '%(name))
            return result
        return func

