#
### $Id: interface.py 17583 2010-04-06 15:01:08Z tmack $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/server/interface.py $
#

from sfa.util.faults import *
from sfa.util.storage import *
from sfa.util.namespace import *
from sfa.trust.gid import GID
from sfa.util.table import SfaTable
from sfa.util.record import SfaRecord
import traceback
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
import sfa.util.soapprotocol as soapprotocol


# GeniLight client support is optional
try:
    from egeni.geniLight_client import *
except ImportError:
    GeniClientLight = None            


##
# In is a dictionary of registry connections keyed on the registry
# hrn

class Interfaces(dict):
    """
    Interfaces is a base class for managing information on the
    peers we are federated with. It is responsible for the following:

    1) Makes sure a record exist in the local registry for the each 
       fedeated peer   
    2) Attepts to fetch and install trusted gids   
    3) Provides connections (xmlrpc or soap) to federated peers
    """

    # fields that must be specified in the config file
    default_fields = {
        'hrn': '',
        'addr': '', 
        'port': '', 
    }

    # defined by the class 
    default_dict = {}

    types = ['authority']

    def __init__(self, api, conf_file, type='authority'):
        if type not in self.types:
            raise SfaInfaildArgument('Invalid type %s: must be in %s' % (type, self.types))    
        dict.__init__(self, {})
        self.api = api
        self.type = type  
        # load config file
        self.interface_info = XmlStorage(conf_file, self.default_dict)
        self.interface_info.load()
        interfaces = self.interface_info.values()[0].values()[0]
        if not isinstance(interfaces, list):
            interfaces = [self.interfaces]
        self.interfaces = {}
        required_fields = self.default_fields.keys()
        for interface in interfaces:
            valid = True
            # skp any interface definition that has a null hrn, 
            # address or port
            for field in required_fields:
                if field not in interface or not interface[field]:
                    valid = False
                    break
            if valid:     
                self.interfaces[interface['hrn']] = interface


    def sync_interfaces(self):
        """
        Install missing trusted gids and db records for our federated
        interfaces
        """     
        # Attempt to get any missing peer gids
        # There should be a gid file in /etc/sfa/trusted_roots for every
        # peer registry found in in the registries.xml config file. If there
        # are any missing gids, request a new one from the peer registry.
        gids_current = self.api.auth.trusted_cert_list
        hrns_current = [gid.get_hrn() for gid in gids_current] 
        hrns_expected = self.interfaces.keys() 
        new_hrns = set(hrns_expected).difference(hrns_current)
        gids = self.get_peer_gids(new_hrns) + gids_current
        # make sure there is a record for every gid
        self.update_db_records(self.type, gids)
        
    def get_peer_gids(self, new_hrns):
        """
        Install trusted gids from the specified interfaces.  
        """
        peer_gids = []
        if not new_hrns:
            return peer_gids
        trusted_certs_dir = self.api.config.get_trustedroots_dir()
        for new_hrn in new_hrns:
            if not new_hrn:
                continue
            # the gid for this interface should already be installed  
            if new_hrn == self.api.config.SFA_INTERFACE_HRN:
                continue
            try:
                # get gid from the registry
                interface_info =  self.interfaces[new_hrn]
                interface = self[new_hrn]
                trusted_gids = interface.get_trusted_certs()
                if trusted_gids:
                    # the gid we want shoudl be the first one in the list, 
                    # but lets make sure
                    for trusted_gid in trusted_gids:
                        # default message
                        message = "interface: %s\t" % (self.api.interface)
                        message += "unable to install trusted gid for %s" % \
                                   (new_hrn) 
                        gid = GID(string=trusted_gids[0])
                        peer_gids.append(gid) 
                        if gid.get_hrn() == new_hrn:
                            gid_filename = os.path.join(trusted_certs_dir, '%s.gid' % new_hrn)
                            gid.save_to_file(gid_filename, save_parents=True)
                            message = "interface: %s\tinstalled trusted gid for %s" % \
                                (self.api.interface, new_hrn)
                        # log the message
                        self.api.logger.info(message)
            except:
                message = "interface: %s\tunable to install trusted gid for %s" % \
                            (self.api.interface, new_hrn) 
                self.api.logger.info(message)
                traceback.print_exc()
        
        # reload the trusted certs list
        self.api.auth.load_trusted_certs()
        return peer_gids

    def update_db_records(self, type, gids):
        """
        Make sure there is a record in the local db for allowed registries
        defined in the config file (registries.xml). Removes old records from
        the db.         
        """
        if not gids: 
            return
        
        # hrns that should have a record
        hrns_expected = [gid.get_hrn() for gid in gids]

        # get hrns that actually exist in the db
        table = SfaTable()
        records = table.find({'type': type, 'pointer': -1})
        hrns_found = [record['hrn'] for record in records]
      
        # remove old records
        for record in records:
            if record['hrn'] not in hrns_expected and \
                record['hrn'] != self.api.config.SFA_INTERFACE_HRN:
                table.remove(record)

        # add new records
        for gid in gids:
            hrn = gid.get_hrn()
            if hrn not in hrns_found:
                record = {
                    'hrn': hrn,
                    'type': type,
                    'pointer': -1, 
                    'authority': get_authority(hrn),
                    'gid': gid.save_to_string(save_parents=True),
                }
                record = SfaRecord(dict=record)
                table.insert(record)
                        
    def get_connections(self):
        """
        read connection details for the trusted peer registries from file return 
        a dictionary of connections keyed on interface hrn. 
        """
        connections = {}
        required_fields = self.default_fields.keys()
        for interface in self.interfaces.values():
            # make sure the required fields are present and not null
            if not all([interface.get(key) for key in required_fields]):
                continue
            
            hrn, address, port = interface['hrn'], interface['addr'], interface['port']
            url = 'http://%(address)s:%(port)s' % locals()
            
            # check which client we should use
            # sfa.util.xmlrpcprotocol is default
            client_type = 'xmlrpcprotocol'
            if interface.has_key('client') and \
               interface['client'] in ['geniclientlight'] and \
               GeniClientLight:
                client_type = 'geniclientlight'
                connections[hrn] = GeniClientLight(url, self.api.key_file, self.api.cert_file) 
            else:
                connections[hrn] = xmlrpcprotocol.get_server(url, self.api.key_file, self.api.cert_file)

        return connections 
