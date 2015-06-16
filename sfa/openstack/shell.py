import sys
import xmlrpclib
import socket
import gettext
from urlparse import urlparse
from sfa.util.sfalogging import logger
from sfa.util.config import Config
from sfa.util.faults import SfaNotImplemented

try:
    from sfa.openstack.client import NovaClient, KeystoneClient, NeutronClient
    has_osclients = True
except:
    logger.error("Please check import of python clients for openstack in sfa/openstack/client.py")
    logger.error("Or install python clients for openstack")
    logger.error("apt-get install python-novaclient python-keystoneclient python-neutronclient python-openstackclient")
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
