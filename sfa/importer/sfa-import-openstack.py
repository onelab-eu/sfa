#!/usr/bin/python
#
##
# Import PLC records into the SFA database. It is indended that this tool be
# run once to create SFA records that reflect the current state of the
# planetlab database.
#
# The import tool assumes that the existing PLC hierarchy should all be part
# of "planetlab.us" (see the root_auth and level1_auth variables below).
#
# Public keys are extracted from the users' SSH keys automatically and used to
# create GIDs. This is relatively experimental as a custom tool had to be
# written to perform conversion from SSH to OpenSSL format. It only supports
# RSA keys at this time, not DSA keys.
##

import os
import getopt
import sys

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn
from sfa.util.plxrn import hostname_to_hrn, slicename_to_hrn, email_to_hrn, hrn_to_pl_slicename
from sfa.storage.table import SfaTable
from sfa.storage.record import SfaRecord
from sfa.trust.certificate import convert_public_key, Keypair
from sfa.trust.gid import create_uuid
from sfa.importer.sfaImport import sfaImport, _cleanup_string
from sfa.util.sfalogging import logger
from sfa.openstack.nova_shell import NovaShell    

def process_options():

   (options, args) = getopt.getopt(sys.argv[1:], '', [])
   for opt in options:
       name = opt[0]
       val = opt[1]


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

def main():

    process_options()
    config = Config()
    sfaImporter = sfaImport()
    logger=sfaImporter.logger
    logger.setLevelFromOptVerbose(config.SFA_API_LOGLEVEL)
    if not config.SFA_REGISTRY_ENABLED:
        sys.exit(0)
    root_auth = config.SFA_REGISTRY_ROOT_AUTH
    interface_hrn = config.SFA_INTERFACE_HRN
    shell = NovaShell(config)
    sfaImporter.create_top_level_records()
    
    # create dict of all existing sfa records
    existing_records = {}
    existing_hrns = []
    key_ids = []
    table = SfaTable()
    results = table.find()
    for result in results:
        existing_records[(result['hrn'], result['type'])] = result
        existing_hrns.append(result['hrn']) 
            
        
    # Get all users
    persons = shell.auth_manager.get_users()
    persons_dict = {}
    keys_filename = config.config_path + os.sep + 'person_keys.py' 
    old_person_keys = load_keys(keys_filename)    
    person_keys = {} 
    for person in persons:
        hrn = config.SFA_INTERFACE_HRN + "." + person.id
        persons_dict[hrn] = person
        old_keys = old_person_keys.get(person.id, [])
        keys = [k.public_key for k in shell.db.key_pair_get_all_by_user(person.id)]
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
            person_record = SfaRecord(hrn=hrn, gid=person_gid, type="user", \
                                          authority=get_authority(hrn))
            logger.info("Import: importing %s " % person_record.summary_string())
            person_record.sync()

    # Get all projects
    projects = shell.get_projects()
    projects_dict = {}
    for project in projects:
        hrn = config.SFA_INTERFACE_HRN + '.' + project.id
        projects_dict[hrn] = project
        if hrn not in existing_hrns or \
        (hrn, 'slice') not in existing_records:
            pkey = Keypair(create=True)
            urn = hrn_to_urn(hrn, 'slice')
            project_gid = sfaImporter.AuthHierarchy.create_gid(urn, create_uuid(), pkey)
            project_record = SfaRecord(hrn=hrn, gid=project_gid, type="slice",
                                       authority=get_authority(hrn))
            projects_dict[project_record['hrn']] = project_record
            logger.info("Import: importing %s " % project_record.summary_string())
            project_record.sync() 
    
    # remove stale records    
    system_records = [interface_hrn, root_auth, interface_hrn + '.slicemanager']
    for (record_hrn, type) in existing_records.keys():
        if record_hrn in system_records:
            continue
        
        record = existing_records[(record_hrn, type)]
        if record['peer_authority']:
            continue

        if type == 'user':
            if record_hrn in persons_dict:
                continue  
        elif type == 'slice':
            if record_hrn in projects_dict:
                continue
        else:
            continue 
        
        record_object = existing_records[(record_hrn, type)]
        record = SfaRecord(dict=record_object)
        logger.info("Import: removing %s " % record.summary_string())
        record.delete()
                                   
    # save pub keys
    logger.info('Import: saving current pub keys')
    save_keys(keys_filename, person_keys)                
        
if __name__ == "__main__":
    main()
