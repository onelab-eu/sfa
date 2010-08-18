### $Id$
### $URL$


from sfa.util.server import SfaServer
from sfa.util.faults import *
from sfa.util.namespace import hrn_to_urn
from sfa.server.interface import Interfaces
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
import sfa.util.soapprotocol as soapprotocol


class Aggregate(SfaServer):

    ##
    # Create a new aggregate object.
    #
    # @param ip the ip address to listen on
    # @param port the port to listen on
    # @param key_file private key filename of registry
    # @param cert_file certificate filename containing public key (could be a GID file)     
    def __init__(self, ip, port, key_file, cert_file):
        SfaServer.__init__(self, ip, port, key_file, cert_file)
        self.server.interface = 'aggregate'

##
# Aggregates is a dictionary of aggregate connections keyed on the aggregate hrn

class Aggregates(Interfaces):

    default_dict = {'aggregates': {'aggregate': [Interfaces.default_fields]}}
 
    def __init__(self, api, conf_file = "/etc/sfa/aggregates.xml"):
        Interfaces.__init__(self, api, conf_file)
        # set up a connection to the local registry
        address = self.api.config.SFA_AGGREGATE_HOST
        port = self.api.config.SFA_AGGREGATE_PORT
        url = 'http://%(address)s:%(port)s' % locals()
        local_aggregate = {'hrn': self.api.hrn,
                           'urn': hrn_to_urn(self.api.hrn, 'authority'),
                           'addr': address,
                           'port': port,
                           'url': url}
        self.interfaces[self.api.hrn] = local_aggregate

        # get connections
        self.update(self.get_connections())
