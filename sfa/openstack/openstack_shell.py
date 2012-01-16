import sys
import xmlrpclib
import socket
from urlparse import urlparse

from sfa.util.sfalogging import logger

class OpenstackShell:
    """
    A simple xmlrpc shell to a myplc instance
    This class can receive all Openstack calls to the underlying testbed
    """
    
    # dont care about limiting calls yet 
    direct_calls = []
    alias_calls = {}


    # use the 'capability' auth mechanism for higher performance when the PLC db is local    
    def __init__ ( self, config ) :
        url = config.SFA_PLC_URL
        # try to figure if the url is local
        hostname=urlparse(url).hostname
        is_local=False
        if hostname == 'localhost': is_local=True
        # otherwise compare IP addresses; 
        # this might fail for any number of reasons, so let's harden that
        try:
            # xxx todo this seems to result in a DNS request for each incoming request to the AM
            # should be cached or improved
            url_ip=socket.gethostbyname(hostname)
            local_ip=socket.gethostbyname(socket.gethostname())
            if url_ip==local_ip: is_local=True
        except:
            pass


        # Openstack provides a RESTful api but it is very limited, so we will
        # ignore it for now and always use the native openstack (nova) library.
        # This of course will not work if sfa is not installed on the same machine
        # as the openstack-compute package.   
        if is_local:
            try:
                from nova.auth.manager import AuthManager, db, context
                direct_access=True
            except:
                direct_access=False
        if is_local and direct_access:
            
            logger.debug('openstack access - native')
            self.auth = context.get_admin_context()
            # AuthManager isnt' really useful for much yet but it's
            # more convenient to use than the db reference which requires
            # a context. Lets hold onto the AuthManager reference for now.
            #self.proxy = AuthManager()
            self.auth_manager = AuthManager()
            self.proxy = db

        else:
            self.auth = None
            self.proxy = None
            logger.debug('openstack access - REST')
            raise SfaNotImplemented('openstack access - Rest')

    def __getattr__(self, name):
        def func(*args, **kwds):
            result=getattr(self.proxy, name)(self.auth, *args, **kwds)
            return result
        return func
