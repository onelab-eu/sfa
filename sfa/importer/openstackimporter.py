import os

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn
from sfa.util.plxrn import hostname_to_hrn, slicename_to_hrn, email_to_hrn, hrn_to_pl_slicename

from sfa.trust.gid import create_uuid    
from sfa.trust.certificate import convert_public_key, Keypair

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegUser, RegSlice, RegNode

from sfa.openstack.openstack_shell import OpenstackShell    

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

    def record_options (self, parser):
        self.logger.debug ("PlImporter no options yet")
        pass

    def run (self, options):
        # we don't have any options for now
        self.logger.info ("PlImporter.run : to do")

        config = Config ()
        interface_hrn = config.SFA_INTERFACE_HRN
        root_auth = config.SFA_REGISTRY_ROOT_AUTH
        shell = OpenstackShell (config)

        # create dict of all existing sfa records
        existing_records = {}
        existing_hrns = []
        key_ids = []
        for record in dbsession.query(RegRecord):
            existing_records[ (record.hrn, record.type,) ] = record
            existing_hrns.append(record.hrn) 
            
        # Get all users
        persons = shell.user_get_all()
        persons_dict = {}
        keys_filename = config.config_path + os.sep + 'person_keys.py' 
        old_person_keys = load_keys(keys_filename)
        person_keys = {} 
        for person in persons:
            hrn = config.SFA_INTERFACE_HRN + "." + person.id
            persons_dict[hrn] = person
            old_keys = old_person_keys.get(person.id, [])
            keys = [k.public_key for k in shell.key_pair_get_all_by_user(person.id)]
            person_keys[person.id] = keys
            update_record = False
            if old_keys != keys:
                update_record = True
            if hrn not in existing_hrns or \
                   (hrn, 'user') not in existing_records or update_record:    
                urn = hrn_to_urn(hrn, 'user')
            
                if keys:
                    try:
                        pkey = convert_public_key(keys[0])
                    except:
                        logger.log_exc('unable to convert public key for %s' % hrn)
                        pkey = Keypair(create=True)
                else:
                    logger.warn("Import: person %s does not have a PL public key"%hrn)
                    pkey = Keypair(create=True) 
                person_gid = sfaImporter.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
                person_record = RegUser ()
                person_record.type='user'
                person_record.hrn=hrn
                person_record.gid=person_gid
                person_record.authority=get_authority(hrn)
                dbsession.add(person_record)
                dbsession.commit()
                logger.info("Import: imported person %s" % person_record)

        # Get all projects
        projects = shell.project_get_all()
        projects_dict = {}
        for project in projects:
            hrn = config.SFA_INTERFACE_HRN + '.' + project.id
            projects_dict[hrn] = project
            if hrn not in existing_hrns or \
            (hrn, 'slice') not in existing_records:
                pkey = Keypair(create=True)
                urn = hrn_to_urn(hrn, 'slice')
                project_gid = sfaImporter.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
                project_record = RegSlice ()
                project_record.type='slice'
                project_record.hrn=hrn
                project_record.gid=project_gid
                project_record.authority=get_authority(hrn)
                dbsession.add(project_record)
                dbsession.commit()
                logger.info("Import: imported slice: %s" % project_record)  
    
        # remove stale records    
        system_records = [interface_hrn, root_auth, interface_hrn + '.slicemanager']
        for (record_hrn, type) in existing_records.keys():
            if record_hrn in system_records:
                continue
        
            record = existing_records[(record_hrn, type)]
            if record.peer_authority:
                continue

            if type == 'user':
                if record_hrn in persons_dict:
                    continue  
            elif type == 'slice':
                if record_hrn in projects_dict:
                    continue
            else:
                continue 
        
            record_object = existing_records[ (record_hrn, type) ]
            logger.info("Import: removing %s " % record)
            dbsession.delete(record_object)
            dbsession.commit()
                                   
        # save pub keys
        logger.info('Import: saving current pub keys')
        save_keys(keys_filename, person_keys)                
        
