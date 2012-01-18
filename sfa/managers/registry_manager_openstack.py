import types
import time 
# for get_key_from_incoming_ip
import tempfile
import os
import commands

from sfa.util.faults import RecordNotFound, AccountNotEnabled, PermissionError, MissingAuthority, \
    UnknownSfaType, ExistingRecord, NonExistingRecord
from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.prefixTree import prefixTree
from sfa.util.xrn import Xrn, get_authority, hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import hrn_to_pl_login_base
from sfa.util.version import version_core
from sfa.util.sfalogging import logger
from sfa.trust.gid import GID 
from sfa.trust.credential import Credential
from sfa.trust.certificate import Certificate, Keypair, convert_public_key
from sfa.trust.gid import create_uuid
from sfa.storage.record import SfaRecord
from sfa.storage.table import SfaTable
from sfa.managers import registry_manager

class RegistryManager(registry_manager.RegistryManager):

    def GetCredential(self, api, xrn, type, is_self=False):
        # convert xrn to hrn     
        if type:
            hrn = urn_to_hrn(xrn)[0]
        else:
            hrn, type = urn_to_hrn(xrn)
            
        # Is this a root or sub authority
        auth_hrn = api.auth.get_authority(hrn)
        if not auth_hrn or hrn == api.config.SFA_INTERFACE_HRN:
            auth_hrn = hrn
        # get record info
        auth_info = api.auth.get_auth_info(auth_hrn)
        table = SfaTable()
        records = table.findObjects({'type': type, 'hrn': hrn})
        if not records:
            raise RecordNotFound(hrn)
        record = records[0]
    
        # verify_cancreate_credential requires that the member lists
        # (researchers, pis, etc) be filled in
        self.driver.augment_records_with_testbed_info (record)
        if not self.driver.is_enabled (record):
              raise AccountNotEnabled(": PlanetLab account %s is not enabled. Please contact your site PI" %(record['email']))
    
        # get the callers gid
        # if this is a self cred the record's gid is the caller's gid
        if is_self:
            caller_hrn = hrn
            caller_gid = record.get_gid_object()
        else:
            caller_gid = api.auth.client_cred.get_gid_caller() 
            caller_hrn = caller_gid.get_hrn()
        
        object_hrn = record.get_gid_object().get_hrn()
        rights = api.auth.determine_user_rights(caller_hrn, record)
        # make sure caller has rights to this object
        if rights.is_empty():
            raise PermissionError(caller_hrn + " has no rights to " + record['name'])
    
        object_gid = GID(string=record['gid'])
        new_cred = Credential(subject = object_gid.get_subject())
        new_cred.set_gid_caller(caller_gid)
        new_cred.set_gid_object(object_gid)
        new_cred.set_issuer_keys(auth_info.get_privkey_filename(), auth_info.get_gid_filename())
        #new_cred.set_pubkey(object_gid.get_pubkey())
        new_cred.set_privileges(rights)
        new_cred.get_privileges().delegate_all_privileges(True)
        if 'expires' in record:
            date = utcparse(record['expires'])
            expires = datetime_to_epoch(date)
            new_cred.set_expiration(int(expires))
        auth_kind = "authority,ma,sa"
        # Parent not necessary, verify with certs
        #new_cred.set_parent(api.auth.hierarchy.get_auth_cred(auth_hrn, kind=auth_kind))
        new_cred.encode()
        new_cred.sign()
    
        return new_cred.save_to_string(save_parents=True)
    
    
    # subject_record describes the subject of the relationships
    # ref_record contains the target values for the various relationships we need to manage
    # (to begin with, this is just the slice x person relationship)
    def update_relations (self, subject_record, ref_record):
        type=subject_record['type']
        if type=='slice':
            self.update_relation(subject_record, 'researcher', ref_record.get('researcher'), 'user')
        
    # field_key is the name of one field in the record, typically 'researcher' for a 'slice' record
    # hrns is the list of hrns that should be linked to the subject from now on
    # target_type would be e.g. 'user' in the 'slice' x 'researcher' example
    def update_relation (self, sfa_record, field_key, hrns, target_type):
        # locate the linked objects in our db
        subject_type=sfa_record['type']
        subject_id=sfa_record['pointer']
        table = SfaTable()
        link_sfa_records = table.find ({'type':target_type, 'hrn': hrns})
        link_ids = [ rec.get('pointer') for rec in link_sfa_records ]
        self.driver.update_relation (subject_type, target_type, subject_id, link_ids)
        

