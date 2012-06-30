import os

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn
from sfa.trust.gid import create_uuid    
from sfa.trust.certificate import convert_public_key, Keypair
from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegUser, RegSlice, RegNode
from sfa.openstack.osxrn import OSXrn
from sfa.openstack.shell import Shell    

def load_keys(filename):
    keys = {}
    tmp_dict = {}
    try:
        execfile(filename, tmp_dict)
        if 'keys' in tmp_dict:
            keys = tmp_dict['keys']
        return keys
    except:
        return keys

def save_keys(filename, keys):
    f = open(filename, 'w')
    f.write("keys = %s" % str(keys))
    f.close()

class OpenstackImporter:

    def __init__ (self, auth_hierarchy, logger):
        self.auth_hierarchy = auth_hierarchy
        self.logger=logger

    def add_options (self, parser):
        self.logger.debug ("OpenstackImporter: no options yet")
        pass

    def run (self, options):
        # we don't have any options for now
        self.logger.info ("OpenstackImporter.run : to do")

        config = Config ()
        interface_hrn = config.SFA_INTERFACE_HRN
        root_auth = config.SFA_REGISTRY_ROOT_AUTH
        shell = Shell (config)

        # create dict of all existing sfa records
        existing_records = {}
        existing_hrns = []
        key_ids = []
        for record in dbsession.query(RegRecord):
            existing_records[ (record.hrn, record.type,) ] = record
            existing_hrns.append(record.hrn) 
            
        # Get all users
        users = shell.auth_manager.users.list()
        users_dict = {}
        keys_filename = config.config_path + os.sep + 'person_keys.py' 
        old_user_keys = load_keys(keys_filename)
        user_keys = {} 
        for user in users:
            auth_hrn = config.SFA_INTERFACE_HRN 
            if user.tenantId is not None:
                tenant = shell.auth_manager.tenants.find(id=user.tenantId)
                auth_hrn = OSXrn(name=tenant.name, auth=config.SFA_INTERFACE_HRN, type='authority').get_hrn()
            hrn = OSXrn(name=user.name, auth=auth_hrn, type='user').get_hrn() 
            users_dict[hrn] = user
            old_keys = old_user_keys.get(hrn, [])
            keys = [k.public_key for k in shell.nova_manager.keypairs.findall(name=hrn)]
            user_keys[hrn] = keys
            update_record = False
            if old_keys != keys:
                update_record = True
            if hrn not in existing_hrns or \
                   (hrn, 'user') not in existing_records or update_record:    
                urn = OSXrn(xrn=hrn, type='user').get_urn()
            
                if keys:
                    try:
                        pkey = convert_public_key(keys[0])
                    except:
                        self.logger.log_exc('unable to convert public key for %s' % hrn)
                        pkey = Keypair(create=True)
                else:
                    self.logger.warn("OpenstackImporter: person %s does not have a PL public key"%hrn)
                    pkey = Keypair(create=True) 
                user_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                user_record = RegUser ()
                user_record.type='user'
                user_record.hrn=hrn
                user_record.gid=user_gid
                user_record.authority=get_authority(hrn)
                dbsession.add(user_record)
                dbsession.commit()
                self.logger.info("OpenstackImporter: imported person %s" % user_record)

        # Get all tenants 
        # A tenant can represent an organizational group (site) or a 
        # slice. If a tenant's authorty/parent matches the root authority it is 
        # considered a group/site. All other tenants are considered slices.         
        tenants = shell.auth_manager.tenants.list()
        tenants_dict = {}
        for tenant in tenants:
            hrn = config.SFA_INTERFACE_HRN + '.' + tenant.name
            tenants_dict[hrn] = tenant
            authority_hrn = OSXrn(xrn=hrn, type='authority').get_authority_hrn()

            if hrn in existing_hrns:
                continue
        
            if authority_hrn == config.SFA_INTERFACE_HRN:
                # import group/site
                record = RegAuthority()
                urn = OSXrn(xrn=hrn, type='authority').get_urn()
                if not self.auth_hierarchy.auth_exists(urn):
                    self.auth_hierarchy.create_auth(urn)
                auth_info = self.auth_hierarchy.get_auth_info(urn)
                gid = auth_info.get_gid_object()
                record.type='authority'
                record.hrn=hrn
                record.gid=gid
                record.authority=get_authority(hrn)
                dbsession.add(record)
                dbsession.commit()
                self.logger.info("OpenstackImporter: imported authority: %s" % record)
                
            else:
                record = RegSlice ()
                urn = OSXrn(xrn=hrn, type='slice').get_urn()
                pkey = Keypair(create=True)
                gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                record.type='slice'
                record.hrn=hrn
                record.gid=gid
                record.authority=get_authority(hrn)
                dbsession.add(record)
                dbsession.commit()
                self.logger.info("OpenstackImporter: imported slice: %s" % record)
                
        # remove stale records    
        system_records = [interface_hrn, root_auth, interface_hrn + '.slicemanager']
        for (record_hrn, type) in existing_records.keys():
            if record_hrn in system_records:
                continue
        
            record = existing_records[(record_hrn, type)]
            if record.peer_authority:
                continue

            if type == 'user':
                if record_hrn in users_dict:
                    continue  
            elif type == 'slice':
                if record_hrn in tenants_dict:
                    continue
            else:
                continue 
        
            record_object = existing_records[ (record_hrn, type) ]
            self.logger.info("OpenstackImporter: removing %s " % record)
            dbsession.delete(record_object)
            dbsession.commit()
                                   
        # save pub keys
        self.logger.info('OpenstackImporter: saving current pub keys')
        save_keys(keys_filename, user_keys)                
        
