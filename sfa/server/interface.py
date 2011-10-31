#from sfa.util.faults import *
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from sfa.util.xml import XML

# GeniLight client support is optional
try:
    from egeni.geniLight_client import *
except ImportError:
    GeniClientLight = None            

class Interface:
    """
    Interface to another SFA service, typically a peer, or the local aggregate
    can retrieve a xmlrpclib.ServerProxy object for issuing calls there
    """
    def __init__(self, hrn, addr, port, client_type='sfa'):
        self.hrn = hrn
        self.addr = addr
        self.port = port
        self.client_type = client_type
  
    def get_url(self):
        address_parts = self.addr.split('/')
        address_parts[0] = address_parts[0] + ":" + str(self.port)
        url =  "http://%s" %  "/".join(address_parts)
        return url

    def get_server(self, key_file, cert_file, timeout=30):
        server = None 
        if  self.client_type ==  'geniclientlight' and GeniClientLight:
            # xxx url and self.api are undefined
            server = GeniClientLight(url, self.api.key_file, self.api.cert_file)
        else:
            server = xmlrpcprotocol.get_server(self.get_url(), key_file, cert_file, timeout) 
 
        return server       
##
# In is a dictionary of registry connections keyed on the registry
# hrn

class Interfaces(dict):
    """
    Interfaces is a base class for managing information on the
    peers we are federated with. Provides connections (xmlrpc or soap) to federated peers
    """

    # fields that must be specified in the config file
    default_fields = {
        'hrn': '',
        'addr': '', 
        'port': '', 
    }

    # defined by the class 
    default_dict = {}

    def __init__(self, conf_file):
        dict.__init__(self, {})
        # load config file
        required_fields = set(self.default_fields.keys())
        self.interface_info = XML(conf_file).todict()
        for value in self.interface_info.values():
            if isinstance(value, list):
                for record in value:
                    if isinstance(record, dict) and \
                      required_fields.issubset(record.keys()):
                        hrn, address, port = record['hrn'], record['addr'], record['port']
                        # sometime this is called at a very early stage with no config loaded
                        # avoid to remember this instance in such a case
                        if not address or not port:
                            continue     
                        interface = Interface(hrn, address, port)
                        self[hrn] = interface   

    def get_server(self, hrn, key_file, cert_file, timeout=30):
        return self[hrn].get_server(key_file, cert_file, timeout)
