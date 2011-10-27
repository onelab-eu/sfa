#
# Registry is a SfaServer that implements the Registry interface
#
from sfa.util.server import SfaServer
from sfa.util.faults import *
from sfa.util.xrn import hrn_to_urn
from sfa.server.interface import Interfaces, Interface
from sfa.util.config import Config 

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
        SfaServer.__init__(self, ip, port, key_file, cert_file,'registry')

##
# Registries is a dictionary of registry connections keyed on the registry
# hrn

class Registries(Interfaces):
    
    default_dict = {'registries': {'registry': [Interfaces.default_fields]}}

    def __init__(self, conf_file = "/etc/sfa/registries.xml"):
        Interfaces.__init__(self, conf_file) 
        sfa_config = Config() 
        if sfa_config.SFA_REGISTRY_ENABLED:
            addr = sfa_config.SFA_REGISTRY_HOST
            port = sfa_config.SFA_REGISTRY_PORT
            hrn = sfa_config.SFA_INTERFACE_HRN
            interface = Interface(hrn, addr, port)
            self[hrn] = interface
