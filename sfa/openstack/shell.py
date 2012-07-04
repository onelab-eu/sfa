import sys
import xmlrpclib
import socket
import gettext
from urlparse import urlparse
from sfa.util.sfalogging import logger
from sfa.util.config import Config

try:
    from sfa.openstack.client import GlanceClient, NovaClient, KeystoneClient
    has_nova = True
except:
    has_nova = False



class Shell:
    """
    A simple native shell to a nova backend. 
    This class can receive all nova calls to the underlying testbed
    """
    
    # dont care about limiting calls yet 
    direct_calls = []
    alias_calls = {}


    # use the 'capability' auth mechanism for higher performance when the PLC db is local    
    def __init__ ( self, config=None) :
        if not config:
            config = Config()
        if has_nova:
            # instantiate managers 
            self.auth_manager = KeystoneClient(config)
            self.image_manager = GlanceClient(config)
            self.nova_manager = NovaClient(config)
        else:
            logger.debug('nova access - REST')
            raise SfaNotImplemented('nova access - Rest')
