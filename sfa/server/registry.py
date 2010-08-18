#
# Registry is a SfaServer that implements the Registry interface
#
### $Id$
### $URL$
#

from sfa.util.server import SfaServer
from sfa.util.faults import *
from sfa.util.namespace import hrn_to_urn
from sfa.server.interface import Interfaces
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
import sfa.util.soapprotocol as soapprotocol
 

##
# Registry is a SfaServer that serves registry and slice operations at PLC.
class Registry(SfaServer):
    ##
    # Create a new registry object.
    #
    # @param ip the ip address to listen on
    # @param port the port to listen on
    # @param key_file private key filename of registry
    # @param cert_file certificate filename containing public key (could be a GID file)
    
    def __init__(self, ip, port, key_file, cert_file):
        SfaServer.__init__(self, ip, port, key_file, cert_file)
        self.server.interface = 'registry' 


##
# Registries is a dictionary of registry connections keyed on the registry
# hrn

class Registries(Interfaces):
    
    default_dict = {'registries': {'registry': [Interfaces.default_fields]}}

    def __init__(self, api, conf_file = "/etc/sfa/registries.xml"):
        Interfaces.__init__(self, api, conf_file) 
        address = self.api.config.SFA_REGISTRY_HOST
        port = self.api.config.SFA_REGISTRY_PORT
        url = 'http://%(address)s:%(port)s' % locals()
        local_registry = {'hrn': self.api.hrn,
                           'urn': hrn_to_urn(self.api.hrn, 'authority'),
                           'addr': address,
                           'port': port,
                           'url': url}
        self.interfaces[self.api.hrn] = local_registry
       
        # get connections
        self.update(self.get_connections()) 
