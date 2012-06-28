import sys
import xmlrpclib
import socket
import gettext
from urlparse import urlparse
from sfa.util.sfalogging import logger
from sfa.util.config import Config

try:
    from nova import db
    from nova import flags
    from nova import context
    from nova.auth.manager import AuthManager
    from nova.compute.manager import ComputeManager
    from nova.network.manager import NetworkManager
    from nova.scheduler.manager import SchedulerManager
    from sfa.openstack.client import GlanceClient, NovaClient
    has_nova = True
except:
    has_nova = False


class InjectContext:
    """
    Wraps the module and injects the context when executing methods 
    """     
    def __init__(self, proxy, context):
        self.proxy = proxy
        self.context = context
    
    def __getattr__(self, name):
        def func(*args, **kwds):
            result=getattr(self.proxy, name)(self.context, *args, **kwds)
            return result
        return func

class NovaShell:
    """
    A simple native shell to a nova backend. 
    This class can receive all nova calls to the underlying testbed
    """
    
    # dont care about limiting calls yet 
    direct_calls = []
    alias_calls = {}


    # use the 'capability' auth mechanism for higher performance when the PLC db is local    
    def __init__ ( self, config ) :
        if not config:
            config = Config()
        self.image_manager = None
        self.nova_manager = None

        if has_nova:
            # instantiate managers 
            self.image_manager = GlanceClient(config)
            self.nova_manager = NovaClient(config)
        else:
            logger.debug('nova access - REST')
            raise SfaNotImplemented('nova access - Rest')
