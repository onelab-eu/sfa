from sfa.util.faults import *
from sfa.server.sfaserver import SfaServer
from sfa.util.xrn import hrn_to_urn
from sfa.server.interface import Interfaces, Interface
from sfa.util.config import Config     

class Aggregate(SfaServer):

    ##
    # Create a new aggregate object.
    #
    # @param ip the ip address to listen on
    # @param port the port to listen on
    # @param key_file private key filename of registry
    # @param cert_file certificate filename containing public key (could be a GID file)     
    def __init__(self, ip, port, key_file, cert_file):
        SfaServer.__init__(self, ip, port, key_file, cert_file,'aggregate')

##
# Aggregates is a dictionary of aggregate connections keyed on the aggregate hrn

class Aggregates(Interfaces):

    default_dict = {'aggregates': {'aggregate': [Interfaces.default_fields]}}
 
    def __init__(self, conf_file = "/etc/sfa/aggregates.xml"):
        Interfaces.__init__(self, conf_file)
        sfa_config = Config() 
        # set up a connection to the local aggregate
        if sfa_config.SFA_AGGREGATE_ENABLED:
            addr = sfa_config.SFA_AGGREGATE_HOST
            port = sfa_config.SFA_AGGREGATE_PORT
            hrn = sfa_config.SFA_INTERFACE_HRN
            interface = Interface(hrn, addr, port)
            self[hrn] = interface
