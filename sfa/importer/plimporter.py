import os

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn
from sfa.util.plxrn import hostname_to_hrn, slicename_to_hrn, email_to_hrn, hrn_to_pl_slicename

from sfa.trust.gid import create_uuid    
from sfa.trust.certificate import convert_public_key, Keypair

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegSlice, RegNode, RegUser, RegKey

from sfa.plc.plshell import PlShell    

def _get_site_hrn(interface_hrn, site):
    # Hardcode 'internet2' into the hrn for sites hosting
    # internet2 nodes. This is a special operation for some vini
    # sites only
    hrn = ".".join([interface_hrn, site['login_base']]) 
    if ".vini" in interface_hrn and interface_hrn.endswith('vini'):
        if site['login_base'].startswith("i2") or site['login_base'].startswith("nlr"):
            hrn = ".".join([interface_hrn, "internet2", site['login_base']])
    return hrn


class PlImporter:

    def __init__ (self, auth_hierarchy, logger):
        self.auth_hierarchy = auth_hierarchy
        self.logger=logger

    def add_options (self, parser):
        # we don't have any options for now
        pass

    # this makes the run method a bit abtruse - out of the way
    def create_special_vini_record (self, interface_hrn):
        # special case for vini
        if ".vini" in interface_hrn and interface_hrn.endswith('vini'):
            # create a fake internet2 site first
            i2site = {'name': 'Internet2', 'login_base': 'internet2', 'site_id': -1}
            site_hrn = _get_site_hrn(interface_hrn, i2site)
            # import if hrn is not in list of existing hrns or if the hrn exists
            # but its not a site record
            if ( 'authority', site_hrn, ) not in self.records_by_type_hrn:
                urn = hrn_to_urn(site_hrn, 'authority')
                if not self.auth_hierarchy.auth_exists(urn):
                    self.auth_hierarchy.create_auth(urn)
                auth_info = self.auth_hierarchy.get_auth_info(urn)
                auth_record = RegAuthority(hrn=site_hrn, gid=auth_info.get_gid_object(),
                                           pointer=site['site_id'],
                                           authority=get_authority(site_hrn))
                auth_record.just_created()
                dbsession.add(auth_record)
                dbsession.commit()
                self.logger.info("PlImporter: Imported authority (vini site) %s"%auth_record)

    def run (self, options):
        config = Config ()
        interface_hrn = config.SFA_INTERFACE_HRN
        root_auth = config.SFA_REGISTRY_ROOT_AUTH
        shell = PlShell (config)

        ######## retrieve all existing SFA objects
        records = dbsession.query(RegRecord)
        # create indexes / hashes by (type,hrn) 
        self.records_by_type_hrn = dict ( [ ( (record.type, record.hrn) , record ) for record in records ] )
        # and by (type,pointer)
        self.records_by_type_pointer = \
            dict ( [ ( (record.type, record.pointer) , record ) for record in records if record.pointer != -1 ] )

        ######## retrieve PLC records
        # Get all plc sites
        # retrieve only required stuf
        sites = shell.GetSites({'peer_id': None, 'enabled' : True},
                               ['site_id','login_base','node_ids','slice_ids','person_ids',])
        # create a hash of sites by login_base
        sites_by_login_base = dict ( [ ( site['login_base'], site ) for site in sites ] )
    
        # Get all plc users
        persons = shell.GetPersons({'peer_id': None, 'enabled': True}, 
                                   ['person_id', 'email', 'key_ids', 'site_ids'])
        # create a hash of persons by person_id
        persons_by_id = dict ( [ ( person['person_id'], person) for person in persons ] )
        
        # Get all plc public keys
        # accumulate key ids for keys retrieval
        key_ids = []
        for person in persons:
            key_ids.extend(person['key_ids'])
        keys = shell.GetKeys( {'peer_id': None, 'key_id': key_ids} )

        # create a hash of keys by key_id
        keys_by_id = dict ( [ ( key['key_id'], key ) for key in keys ] ) 

        # create a dict person_id -> [ (plc)keys ]
        keys_by_person_id = {} 
        for person in persons:
            pubkeys = []
            for key_id in person['key_ids']:
                pubkeys.append(keys_by_id[key_id])
            keys_by_person_id[person['person_id']] = pubkeys

        # Get all plc nodes  
        nodes = shell.GetNodes( {'peer_id': None}, ['node_id', 'hostname', 'site_id'])
        # create hash by node_id
        nodes_by_id = dict ( [ ( node['node_id'], node, ) for node in nodes ] )

        # Get all plc slices
        slices = shell.GetSlices( {'peer_id': None}, ['slice_id', 'name'])
        # create hash by slice_id
        slices_by_id = dict ( [ (slice['slice_id'], slice ) for slice in slices ] )

        # isolate special vini case in separate method
        self.create_special_vini_record (interface_hrn)

        # start importing 
        for site in sites:
            site_hrn = _get_site_hrn(interface_hrn, site)
    
            # import if hrn is not in list of existing hrns or if the hrn exists
            # but its not a site record
            if ( 'authority', site_hrn, ) not in self.records_by_type_hrn:
                try:
                    urn = hrn_to_urn(site_hrn, 'authority')
                    if not self.auth_hierarchy.auth_exists(urn):
                        self.auth_hierarchy.create_auth(urn)
                    auth_info = self.auth_hierarchy.get_auth_info(urn)
                    auth_record = RegAuthority(hrn=site_hrn, gid=auth_info.get_gid_object(),
                                               pointer=site['site_id'],
                                               authority=get_authority(site_hrn))
                    auth_record.just_created()
                    dbsession.add(auth_record)
                    dbsession.commit()
                    self.logger.info("PlImporter: imported authority (site) : %s" % auth_record)  
                except:
                    # if the site import fails then there is no point in trying to import the
                    # site's child records (node, slices, persons), so skip them.
                    self.logger.log_exc("PlImporter: failed to import site. Skipping child records") 
                    continue 
             
            # import node records
            for node_id in site['node_ids']:
                if node_id not in nodes_by_id:
                    continue 
                node = nodes_by_id[node_id]
                site_auth = get_authority(site_hrn)
                site_name = get_leaf(site_hrn)
                hrn =  hostname_to_hrn(site_auth, site_name, node['hostname'])
                if len(hrn) > 64:
                    hrn = hrn[:64]
                if ( 'node', hrn, ) not in self.records_by_type_hrn:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(hrn, 'node')
                        node_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        node_record = RegNode (hrn=hrn, gid=node_gid, 
                                               pointer =node['node_id'],
                                               authority=get_authority(hrn))
                        node_record.just_created()
                        dbsession.add(node_record)
                        dbsession.commit()
                        self.logger.info("PlImporter: imported node: %s" % node_record)  
                    except:
                        self.logger.log_exc("PlImporter: failed to import node") 
                    

            # import slices
            for slice_id in site['slice_ids']:
                if slice_id not in slices_by_id:
                    continue 
                slice = slices_by_id[slice_id]
                hrn = slicename_to_hrn(interface_hrn, slice['name'])
                if ( 'slice', hrn, ) not in self.records_by_type_hrn:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(hrn, 'slice')
                        slice_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        slice_record = RegSlice (hrn=hrn, gid=slice_gid, 
                                                 pointer=slice['slice_id'],
                                                 authority=get_authority(hrn))
                        slice_record.just_created()
                        dbsession.add(slice_record)
                        dbsession.commit()
                        self.logger.info("PlImporter: imported slice: %s" % slice_record)  
                    except:
                        self.logger.log_exc("PlImporter: failed to  import slice")

            # import persons
            for person_id in site['person_ids']:
                if person_id not in persons_by_id:
                    self.logger.warning ("PlImporter: skipping person %s"%person_id)
                    continue 
                person = persons_by_id[person_id]
                hrn = email_to_hrn(site_hrn, person['email'])
                if len(hrn) > 64:
                    hrn = hrn[:64]
    
                previous_record = self.records_by_type_hrn.get( ( 'user', hrn, ) )
                if not previous_record:
                    previous_record = self.records_by_type_pointer.get ( ('user', person_id,) )
                # if user's primary key has changed then we need to update the 
                # users gid by forcing an update here
                plc_keys = []
                sfa_keys = []
                if previous_record:
                    sfa_keys = previous_record.reg_keys
                if person_id in keys_by_person_id:
                    plc_keys = keys_by_person_id[person_id]
                update_record = False
                def key_in_list (key,sfa_keys):
                    for reg_key in sfa_keys:
                        if reg_key.key==key['key']: return True
                    return False
                for key in plc_keys:
                    if not key_in_list (key,sfa_keys):
                        update_record = True 
    
                if not previous_record or update_record:
                    try:
                        pubkey=None
                        if 'key_ids' in person and person['key_ids']:
                            # randomly pick first key in set
                            pubkey = plc_keys[0]
                            try:
                                pkey = convert_public_key(pubkey['key'])
                            except:
                                self.logger.warn('PlImporter: unable to convert public key for %s' % hrn)
                                pkey = Keypair(create=True)
                        else:
                            # the user has no keys. Creating a random keypair for the user's gid
                            self.logger.warn("PlImporter: person %s does not have a PL public key"%hrn)
                            pkey = Keypair(create=True)
                        urn = hrn_to_urn(hrn, 'user')
                        person_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        if previous_record: 
                            previous_record.gid=person_gid
                            if pubkey: previous_record.reg_keys=[ RegKey (pubkey['key'], pubkey['key_id'])]
                            self.logger.info("PlImporter: updated person: %s" % previous_record)
                        else:
                            new_record = RegUser (hrn=hrn, gid=person_gid, 
                                                  pointer=person['person_id'], 
                                                  authority=get_authority(hrn),
                                                  email=person['email'])
                            if pubkey: 
                                new_record.reg_keys=[RegKey (pubkey['key'], pubkey['key_id'])]
                            else:
                                logger.warning("No key found for user %s"%new_record)
                            dbsession.add (new_record)
                            dbsession.commit()
                            self.logger.info("PlImporter: imported person: %s" % new_record)
                    except:
                        self.logger.log_exc("PlImporter: failed to import person.") 
    
        # remove stale records    
        system_records = [interface_hrn, root_auth, interface_hrn + '.slicemanager']
        for record in records:
            record_hrn=record.hrn
            if record_hrn in system_records:
                continue
            if record.peer_authority:
                continue
            type=record.type
            hrn=record.hrn
            # dont delete vini's internet2 placeholdder record
            # normally this would be deleted becuase it does not have a plc record 
            if ".vini" in interface_hrn and interface_hrn.endswith('vini') and \
               record_hrn.endswith("internet2"):     
                continue
    
            found = False
            
            if isinstance (record, RegAuthority):
                for site in sites:
                    site_hrn = interface_hrn + "." + site['login_base']
                    if site_hrn == record_hrn and site['site_id'] == record.pointer:
                        found = True
                        break

            elif isinstance (record, RegUser):
                login_base = get_leaf(get_authority(record_hrn))
                username = get_leaf(record_hrn)
                if login_base in sites_by_login_base:
                    site = sites_by_login_base[login_base]
                    for person in persons:
                        tmp_username = person['email'].split("@")[0]
                        alt_username = person['email'].split("@")[0].replace(".", "_").replace("+", "_")
                        if username in [tmp_username, alt_username] and \
                           site['site_id'] in person['site_ids'] and \
                           person['person_id'] == record.pointer:
                            found = True
                            break
        
            elif isinstance (record, RegSlice):
                slicename = hrn_to_pl_slicename(record_hrn)
                for slice in slices:
                    if slicename == slice['name'] and \
                       slice['slice_id'] == record.pointer:
                        found = True
                        break    
 
            elif isinstance (record, RegNode):
                login_base = get_leaf(get_authority(record_hrn))
                nodename = Xrn.unescape(get_leaf(record_hrn))
                if login_base in sites_by_login_base:
                    site = sites_by_login_base[login_base]
                    for node in nodes:
                        tmp_nodename = node['hostname']
                        if tmp_nodename == nodename and \
                           node['site_id'] == site['site_id'] and \
                           node['node_id'] == record.pointer:
                            found = True
                            break  
            else:
                continue 
        
            if not found:
                try:
                    record_object = self.records_by_type_hrn[ ( type, record_hrn, ) ]
                    self.logger.info("PlImporter: deleting record: %s" % record)
                    dbsession.delete(record_object)
                    dbsession.commit()
                except:
                    self.logger.log_exc("PlImporter: failded to delete record")                    

#        # save pub keys
#        self.logger.info('Import: saving current pub keys')
#        save_keys(keys_filename, person_keys)                
        
