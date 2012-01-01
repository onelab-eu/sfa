#
# The import tool assumes that the existing PLC hierarchy should all be part
# of "planetlab.us" (see the root_auth and level1_auth variables below).
#
# Public keys are extracted from the users' SSH keys automatically and used to
# create GIDs. This is relatively experimental as a custom tool had to be
# written to perform conversion from SSH to OpenSSL format. It only supports
# RSA keys at this time, not DSA keys.
##

from sfa.util.sfalogging import _SfaLogger
from sfa.util.xrn import get_authority, hrn_to_urn
from sfa.util.plxrn import email_to_hrn
from sfa.util.config import Config
from sfa.trust.certificate import convert_public_key, Keypair
from sfa.trust.trustedroots import TrustedRoots
from sfa.trust.hierarchy import Hierarchy
from sfa.trust.gid import create_uuid
from sfa.storage.table import SfaTable
from sfa.storage.record import SfaRecord
from sfa.storage.table import SfaTable


def _un_unicode(str):
   if isinstance(str, unicode):
       return str.encode("ascii", "ignore")
   else:
       return str

def _cleanup_string(str):
    # pgsql has a fit with strings that have high ascii in them, so filter it
    # out when generating the hrns.
    tmp = ""
    for c in str:
        if ord(c) < 128:
            tmp = tmp + c
    str = tmp

    str = _un_unicode(str)
    str = str.replace(" ", "_")
    str = str.replace(".", "_")
    str = str.replace("(", "_")
    str = str.replace("'", "_")
    str = str.replace(")", "_")
    str = str.replace('"', "_")
    return str

class sfaImport:

    def __init__(self):
       self.logger = _SfaLogger(logfile='/var/log/sfa_import.log', loggername='importlog')
       self.AuthHierarchy = Hierarchy()
       self.table = SfaTable()     
       self.config = Config()
       self.TrustedRoots = TrustedRoots(Config.get_trustedroots_dir(self.config))
       self.root_auth = self.config.SFA_REGISTRY_ROOT_AUTH
       # should use a driver instead...
       from sfa.plc.plshell import PlShell
       # how to connect to planetlab 
       self.shell = PlShell (self.config)

    def create_top_level_records(self):
        """
        Create top level and interface records
        """
        # create root authority
        interface_hrn = self.config.SFA_INTERFACE_HRN
        self.create_top_level_auth_records(interface_hrn)

        # create s user record for the slice manager
        self.create_sm_client_record()

        # create interface records
        self.logger.info("Import: creating interface records")
        self.create_interface_records()

        # add local root authority's cert  to trusted list
        self.logger.info("Import: adding " + interface_hrn + " to trusted list")
        authority = sfaImporter.AuthHierarchy.get_auth_info(interface_hrn)
        self.TrustedRoots.add_gid(authority.get_gid_object())

    def create_top_level_auth_records(self, hrn):
        """
        Create top level db records (includes root and sub authorities (local/remote)
        """
        # make sure parent exists
        parent_hrn = get_authority(hrn)
        if not parent_hrn:
            parent_hrn = hrn
        if not parent_hrn == hrn:
            self.create_top_level_auth_records(parent_hrn)

        # enxure key and cert exists:
        self.AuthHierarchy.create_top_level_auth(hrn)    
        # create the db record if it doesnt already exist    
        auth_info = self.AuthHierarchy.get_auth_info(hrn)
        table = SfaTable()
        auth_record = table.find({'type': 'authority', 'hrn': hrn})

        if not auth_record:
            auth_record = SfaRecord(hrn=hrn, gid=auth_info.get_gid_object(), type="authority", pointer=-1)
            auth_record['authority'] = get_authority(auth_record['hrn'])
            self.logger.info("Import: inserting authority record for %s"%hrn)
            table.insert(auth_record)

    def create_sm_client_record(self):
        """
        Create a user record for the Slicemanager service.
        """
        hrn = self.config.SFA_INTERFACE_HRN + '.slicemanager'
        urn = hrn_to_urn(hrn, 'user')
        if not self.AuthHierarchy.auth_exists(urn):
            self.logger.info("Import: creating Slice Manager user")
            self.AuthHierarchy.create_auth(urn)

        auth_info = self.AuthHierarchy.get_auth_info(hrn)
        table = SfaTable()
        sm_user_record = table.find({'type': 'user', 'hrn': hrn})
        if not sm_user_record:
            record = SfaRecord(hrn=hrn, gid=auth_info.get_gid_object(), type="user", pointer=-1)
            record['authority'] = get_authority(record['hrn'])
            table.insert(record)    

    def create_interface_records(self):
        """
        Create a record for each SFA interface
        """
        # just create certs for all sfa interfaces even if they
        # arent enabled
        interface_hrn = self.config.SFA_INTERFACE_HRN
        interfaces = ['authority+sa', 'authority+am', 'authority+sm']
        table = SfaTable()
        auth_info = self.AuthHierarchy.get_auth_info(interface_hrn)
        pkey = auth_info.get_pkey_object()
        for interface in interfaces:
            interface_record = table.find({'type': interface, 'hrn': interface_hrn})
            if not interface_record:
                self.logger.info("Import: interface %s %s " % (interface_hrn, interface))
                urn = hrn_to_urn(interface_hrn, interface)
                gid = self.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
                record = SfaRecord(hrn=interface_hrn, gid=gid, type=interface, pointer=-1)  
                record['authority'] = get_authority(interface_hrn)
                table.insert(record) 
                                
    def import_person(self, parent_hrn, person):
        """
        Register a user record 
        """
        hrn = email_to_hrn(parent_hrn, person['email'])

        # ASN.1 will have problems with hrn's longer than 64 characters
        if len(hrn) > 64:
            hrn = hrn[:64]

        self.logger.info("Import: person %s"%hrn)
        key_ids = []
        if 'key_ids' in person and person['key_ids']:
            key_ids = person["key_ids"]
            # get the user's private key from the SSH keys they have uploaded
            # to planetlab
            keys = self.shell.GetKeys(key_ids)
            key = keys[0]['key']
            pkey = None
            try:
                pkey = convert_public_key(key)
            except:
                self.logger.warn('unable to convert public key for %s' % hrn) 
            if not pkey:
                pkey = Keypair(create=True)
        else:
            # the user has no keys
            self.logger.warn("Import: person %s does not have a PL public key"%hrn)
            # if a key is unavailable, then we still need to put something in the
            # user's GID. So make one up.
            pkey = Keypair(create=True)

        # create the gid
        urn = hrn_to_urn(hrn, 'user')
        person_gid = self.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
        table = SfaTable()
        person_record = SfaRecord(hrn=hrn, gid=person_gid, type="user", pointer=person['person_id'])
        person_record['authority'] = get_authority(person_record['hrn'])
        existing_records = table.find({'hrn': hrn, 'type': 'user', 'pointer': person['person_id']})
        if not existing_records:
            table.insert(person_record)
        else:
            self.logger.info("Import: %s exists, updating " % hrn)
            existing_record = existing_records[0]
            person_record['record_id'] = existing_record['record_id']
            table.update(person_record)

    def import_slice(self, parent_hrn, slice):
        slicename = slice['name'].split("_",1)[-1]
        slicename = _cleanup_string(slicename)

        if not slicename:
            self.logger.error("Import: failed to parse slice name %s" %slice['name'])
            return

        hrn = parent_hrn + "." + slicename
        self.logger.info("Import: slice %s"%hrn)

        pkey = Keypair(create=True)
        urn = hrn_to_urn(hrn, 'slice')
        slice_gid = self.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
        slice_record = SfaRecord(hrn=hrn, gid=slice_gid, type="slice", pointer=slice['slice_id'])
        slice_record['authority'] = get_authority(slice_record['hrn'])
        table = SfaTable()
        existing_records = table.find({'hrn': hrn, 'type': 'slice', 'pointer': slice['slice_id']})
        if not existing_records:
            table.insert(slice_record)
        else:
            self.logger.info("Import: %s exists, updating " % hrn)
            existing_record = existing_records[0]
            slice_record['record_id'] = existing_record['record_id']
            table.update(slice_record)

    def import_node(self, hrn, node):
        self.logger.info("Import: node %s" % hrn)
        # ASN.1 will have problems with hrn's longer than 64 characters
        if len(hrn) > 64:
            hrn = hrn[:64]

        table = SfaTable()
        node_record = table.find({'type': 'node', 'hrn': hrn})
        pkey = Keypair(create=True)
        urn = hrn_to_urn(hrn, 'node')
        node_gid = self.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
        node_record = SfaRecord(hrn=hrn, gid=node_gid, type="node", pointer=node['node_id'])
        node_record['authority'] = get_authority(node_record['hrn'])
        existing_records = table.find({'hrn': hrn, 'type': 'node', 'pointer': node['node_id']})
        if not existing_records:
            table.insert(node_record)
        else:
            self.logger.info("Import: %s exists, updating " % hrn)
            existing_record = existing_records[0]
            node_record['record_id'] = existing_record['record_id']
            table.update(node_record)

    
    def import_site(self, hrn, site):
        urn = hrn_to_urn(hrn, 'authority')
        self.logger.info("Import: site %s"%hrn)

        # create the authority
        if not self.AuthHierarchy.auth_exists(urn):
            self.AuthHierarchy.create_auth(urn)

        auth_info = self.AuthHierarchy.get_auth_info(urn)

        table = SfaTable()
        auth_record = SfaRecord(hrn=hrn, gid=auth_info.get_gid_object(), type="authority", pointer=site['site_id'])
        auth_record['authority'] = get_authority(auth_record['hrn'])
        existing_records = table.find({'hrn': hrn, 'type': 'authority', 'pointer': site['site_id']})
        if not existing_records:
            table.insert(auth_record)
        else:
            self.logger.info("Import: %s exists, updating " % hrn)
            existing_record = existing_records[0]
            auth_record['record_id'] = existing_record['record_id']
            table.update(auth_record)

        return hrn


    def delete_record(self, hrn, type):
        # delete the record
        table = SfaTable()
        record_list = table.find({'type': type, 'hrn': hrn})
        for record in record_list:
            self.logger.info("Import: removing record %s %s" % (type, hrn))
            table.remove(record)        
