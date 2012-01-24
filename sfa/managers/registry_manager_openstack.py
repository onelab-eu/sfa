import types
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

from sfa.storage.persistentobjs import make_record,RegRecord
from sfa.storage.alchemy import dbsession

from sfa.managers.registry_manager import RegistryManager

class RegistryManager(RegistryManager):

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
        auth_info = api.auth.get_auth_info(auth_hrn)
        # get record info
        record=dbsession.query(RegRecord).filter_by(type=type,hrn=hrn).first()
        if not record:
            raise RecordNotFound("hrn=%s, type=%s"%(hrn,type))
    
        # verify_cancreate_credential requires that the member lists
        # (researchers, pis, etc) be filled in
        logger.debug("get credential before augment dict, keys=%s"%record.__dict__.keys())
        self.driver.augment_records_with_testbed_info (record.__dict__)
        logger.debug("get credential after augment dict, keys=%s"%record.__dict__.keys())
        if not self.driver.is_enabled (record.__dict__):
              raise AccountNotEnabled(": PlanetLab account %s is not enabled. Please contact your site PI" %(record.email))
    
        # get the callers gid
        # if this is a self cred the record's gid is the caller's gid
        if is_self:
            caller_hrn = hrn
            caller_gid = record.get_gid_object()
        else:
            caller_gid = api.auth.client_cred.get_gid_caller() 
            caller_hrn = caller_gid.get_hrn()
        
        object_hrn = record.get_gid_object().get_hrn()
        rights = api.auth.determine_user_rights(caller_hrn, record.__dict__)
        # make sure caller has rights to this object
        if rights.is_empty():
            raise PermissionError(caller_hrn + " has no rights to " + record.hrn)
    
        object_gid = GID(string=record.gid)
        new_cred = Credential(subject = object_gid.get_subject())
        new_cred.set_gid_caller(caller_gid)
        new_cred.set_gid_object(object_gid)
        new_cred.set_issuer_keys(auth_info.get_privkey_filename(), auth_info.get_gid_filename())
        #new_cred.set_pubkey(object_gid.get_pubkey())
        new_cred.set_privileges(rights)
        new_cred.get_privileges().delegate_all_privileges(True)
        if hasattr(record,'expires'):
            date = utcparse(record.expires)
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
    def update_relations (self, subject_obj, ref_obj):
        type=subject_obj.type
        if type=='slice':
            self.update_relation(subject_obj, 'researcher', ref_obj.researcher, 'user')
        
    # field_key is the name of one field in the record, typically 'researcher' for a 'slice' record
    # hrns is the list of hrns that should be linked to the subject from now on
    # target_type would be e.g. 'user' in the 'slice' x 'researcher' example
    def update_relation (self, record_obj, field_key, hrns, target_type):
        # locate the linked objects in our db
        subject_type=record_obj.type
        subject_id=record_obj.pointer
        # get the 'pointer' field of all matching records
        link_id_tuples = dbsession.query(RegRecord.pointer).filter_by(type=target_type).filter(RegRecord.hrn.in_(hrns)).all()
        # sqlalchemy returns named tuples for columns
        link_ids = [ tuple.pointer for tuple in link_id_tuples ]
        self.driver.update_relation (subject_type, target_type, subject_id, link_ids)

