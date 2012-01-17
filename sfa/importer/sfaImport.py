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
from sfa.storage.persistentobjs import RegRecord
from sfa.storage.alchemy import dbsession

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
       self.config = Config()
       self.TrustedRoots = TrustedRoots(Config.get_trustedroots_dir(self.config))
       self.root_auth = self.config.SFA_REGISTRY_ROOT_AUTH

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
        authority = self.AuthHierarchy.get_auth_info(interface_hrn)
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

        # ensure key and cert exists:
        self.AuthHierarchy.create_top_level_auth(hrn)    
        # create the db record if it doesnt already exist    
        auth_info = self.AuthHierarchy.get_auth_info(hrn)
        auth_record = RegRecord("authority", hrn=hrn, gid=auth_info.get_gid_object(), 
                                authority=get_authority(hrn))
        auth_record.just_created()
        self.logger.info("Import: importing auth %s " % auth_record)
        dbsession.add (auth_record)
        dbsession.commit()

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
        user_record = RegRecord("user", hrn=hrn, gid=auth_info.get_gid_object(), \
                                   authority=get_authority(hrn))
        user_record.just_created()
        self.logger.info("Import: importing user %s " % user_record)
        dbsession.add (user_record)
        dbsession.commit()

    def create_interface_records(self):
        """
        Create a record for each SFA interface
        """
        # just create certs for all sfa interfaces even if they
        # arent enabled
        hrn = self.config.SFA_INTERFACE_HRN
        interfaces = ['authority+sa', 'authority+am', 'authority+sm']
        auth_info = self.AuthHierarchy.get_auth_info(hrn)
        pkey = auth_info.get_pkey_object()
        for interface in interfaces:
            urn = hrn_to_urn(hrn, interface)
            gid = self.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
            interface_record = RegRecord(interface, hrn=hrn, gid = gid, 
                                         authority=get_authority(hrn))
            interface_record.just_created()
            self.logger.info("Import: importing %s " % interface_record)
            dbsession.add (interface_record)
            dbsession.commit()
             
    def delete_record(self, hrn, type):
        # delete the record
        for rec in dbsession.query(RegRecord).filter_by(type=type,hrn=hrn):
           del rec
        dbsession.commit()
