import sys
import xmlrpclib
import socket
from urlparse import urlparse
from sfa.util.sfalogging import logger
try:
    from nova.auth.manager import AuthManager
    from nova.compute.manager import ComputeManager
    from nova.network.manager import NetworkManager
    from nova.scheduler.manager import SchedulerManager
    has_nova = True
except:
    has_nova = False
 
class NovaShell:
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


        if is_local and has_nova:
            logger.debug('nova access - native')
            # load the config
            flags.FLAGS(['foo', '--flagfile=/etc/nova/nova.conf', 'foo', 'foo'])
            self.auth = context.get_admin_context()
            self.proxy = db
        else:
            self.auth = None
            self.proxy = None
            logger.debug('nova access - REST')
            raise SfaNotImplemented('nova access - Rest')

    def __getattr__(self, name):
        def func(*args, **kwds):
            result=getattr(self.proxy, name)(self.auth, *args, **kwds)
            return result
        return func
