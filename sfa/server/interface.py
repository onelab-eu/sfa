from sfa.util.faults import *
from sfa.util.storage import XmlStorage
import sfa.util.xmlrpcprotocol as xmlrpcprotocol

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
        self.interface_info = XmlStorage(conf_file, self.default_dict)
        self.interface_info.load()
        records = self.interface_info.values()[0]
        if not isinstance(records, list):
            records = [records]
        
        required_fields = self.default_fields.keys()
        for record in records:
            if not record or not set(required_fields).issubset(record.keys()):
                continue
            # port is appended onto the domain, before the path. Should look like:
            # http://domain:port/path
            hrn, address, port = record['hrn'], record['addr'], record['port']
            interface = Interface(hrn, address, port) 
            self[hrn] = interface

    def get_server(self, hrn, key_file, cert_file, timeout=30):
        return self[hrn].get_server(key_file, cert_file, timeout)
