import sys
import xmlrpclib
import socket
import gettext
from urlparse import urlparse
from sfa.util.sfalogging import logger
from sfa.util.config import Config
try:
    from sfa.openstack.client import NovaClient, KeystoneClient, NeutronClient
    has_osclients = True
except:
    has_osclients = False

class Shell:
    """
    This class can receive all OpenStack calls to the underlying testbed
    """
    # dont care about limiting calls yet 
    direct_calls = []
    alias_calls = {}

    # use the 'capability' auth mechanism for higher performance when the PLC db is local    
    def __init__ ( self, config=None) :
        if not config:
            config = Config()
        if has_osclients:
            # instantiate managers 
            self.auth_manager = KeystoneClient(config=config)
            self.compute_manager = NovaClient(config=config)
            self.network_manager = NeutronClient(config=config)
        else:
            logger.debug('OpenStack Access - REST')
            raise SfaNotImplemented('OpenStack Access - REST')
