#
# PlanetLab importer
# 
# requirements
# 
# read the planetlab database and update the local registry database accordingly
# (in other words, with this testbed, the SFA registry is *not* authoritative)
# so we update the following collections
# . authorities                 (from pl sites)
# . node                        (from pl nodes)
# . users+keys                  (from pl persons and attached keys)
#                       known limitation : *one* of the ssh keys is chosen at random here
#                       xxx todo/check xxx at the very least, when a key is known to the registry 
#                       and is still current in plc
#                       then we should definitely make sure to keep that one in sfa...
# . slice+researchers           (from pl slices and attached users)
# 

import os

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn

from sfa.trust.gid import create_uuid    
from sfa.trust.certificate import convert_public_key, Keypair

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegSlice, RegNode, RegUser, RegKey

from sfa.planetlab.plshell import PlShell    
from sfa.planetlab.plxrn import hostname_to_hrn, slicename_to_hrn, email_to_hrn, hrn_to_pl_slicename

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

    # hrn hash is initialized from current db
    # remember just-created records as we go
    # xxx might make sense to add a UNIQUE constraint in the db itself
    def remember_record_by_hrn (self, record):
        tuple = (record.type, record.hrn)
        if tuple in self.records_by_type_hrn:
            self.logger.warning ("PlImporter.remember_record_by_hrn: duplicate (%s,%s)"%tuple)
            return
        self.records_by_type_hrn [ tuple ] = record

    # ditto for pointer hash
    def remember_record_by_pointer (self, record):
        if record.pointer == -1:
            self.logger.warning ("PlImporter.remember_record_by_pointer: pointer is void")
            return
        tuple = (record.type, record.pointer)
        if tuple in self.records_by_type_pointer:
            self.logger.warning ("PlImporter.remember_record_by_pointer: duplicate (%s,%s)"%tuple)
            return
        self.records_by_type_pointer [ ( record.type, record.pointer,) ] = record

    def remember_record (self, record):
        self.remember_record_by_hrn (record)
        self.remember_record_by_pointer (record)

    def locate_by_type_hrn (self, type, hrn):
        return self.records_by_type_hrn.get ( (type, hrn), None)

    def locate_by_type_pointer (self, type, pointer):
        return self.records_by_type_pointer.get ( (type, pointer), None)

    # a convenience/helper function to see if a record is already known
    # a former, broken, attempt (in 2.1-9) had been made 
    # to try and use 'pointer' as a first, most significant attempt
    # the idea being to preserve stuff as much as possible, and thus 
    # to avoid creating a new gid in the case of a simple hrn rename
    # however this of course doesn't work as the gid depends on the hrn...
    #def locate (self, type, hrn=None, pointer=-1):
    #    if pointer!=-1:
    #        attempt = self.locate_by_type_pointer (type, pointer)
    #        if attempt : return attempt
    #    if hrn is not None:
    #        attempt = self.locate_by_type_hrn (type, hrn,)
    #        if attempt : return attempt
    #    return None

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
                self.remember_record ( site_record )

    def run (self, options):
        config = Config ()
        interface_hrn = config.SFA_INTERFACE_HRN
        root_auth = config.SFA_REGISTRY_ROOT_AUTH
        shell = PlShell (config)

        ######## retrieve all existing SFA objects
        all_records = dbsession.query(RegRecord).all()

        # create hash by (type,hrn) 
        # we essentially use this to know if a given record is already known to SFA 
        self.records_by_type_hrn = \
            dict ( [ ( (record.type, record.hrn) , record ) for record in all_records ] )
        # create hash by (type,pointer) 
        self.records_by_type_pointer = \
            dict ( [ ( (record.type, record.pointer) , record ) for record in all_records 
                     if record.pointer != -1] )

        # initialize record.stale to True by default, then mark stale=False on the ones that are in use
        for record in all_records: record.stale=True

        ######## retrieve PLC data
        # Get all plc sites
        # retrieve only required stuf
        sites = shell.GetSites({'peer_id': None, 'enabled' : True},
                               ['site_id','login_base','node_ids','slice_ids','person_ids',])
        # create a hash of sites by login_base
#        sites_by_login_base = dict ( [ ( site['login_base'], site ) for site in sites ] )
        # Get all plc users
        persons = shell.GetPersons({'peer_id': None, 'enabled': True}, 
                                   ['person_id', 'email', 'key_ids', 'site_ids', 'role_ids'])
        # create a hash of persons by person_id
        persons_by_id = dict ( [ ( person['person_id'], person) for person in persons ] )
        # Get all plc public keys
        # accumulate key ids for keys retrieval
        key_ids = []
        for person in persons:
            key_ids.extend(person['key_ids'])
        keys = shell.GetKeys( {'peer_id': None, 'key_id': key_ids,
                               'key_type': 'ssh'} )
        # create a hash of keys by key_id
        keys_by_id = dict ( [ ( key['key_id'], key ) for key in keys ] ) 
        # create a dict person_id -> [ (plc)keys ]
        keys_by_person_id = {} 
        for person in persons:
            pubkeys = []
            for key_id in person['key_ids']:
                # by construction all the keys we fetched are ssh keys
                # so gpg keys won't be in there
                try:
                    key = keys_by_id[key_id]
                    pubkeys.append(key)
                except:
                    self.logger.warning("Could not spot key %d - probably non-ssh"%key_id)
            keys_by_person_id[person['person_id']] = pubkeys
        # Get all plc nodes  
        nodes = shell.GetNodes( {'peer_id': None}, ['node_id', 'hostname', 'site_id'])
        # create hash by node_id
        nodes_by_id = dict ( [ ( node['node_id'], node, ) for node in nodes ] )
        # Get all plc slices
        slices = shell.GetSlices( {'peer_id': None}, ['slice_id', 'name', 'person_ids'])
        # create hash by slice_id
        slices_by_id = dict ( [ (slice['slice_id'], slice ) for slice in slices ] )

        # isolate special vini case in separate method
        self.create_special_vini_record (interface_hrn)

        # start importing 
        for site in sites:
            site_hrn = _get_site_hrn(interface_hrn, site)
            # import if hrn is not in list of existing hrns or if the hrn exists
            # but its not a site record
            site_record=self.locate_by_type_hrn ('authority', site_hrn)
            if not site_record:
                try:
                    urn = hrn_to_urn(site_hrn, 'authority')
                    if not self.auth_hierarchy.auth_exists(urn):
                        self.auth_hierarchy.create_auth(urn)
                    auth_info = self.auth_hierarchy.get_auth_info(urn)
                    site_record = RegAuthority(hrn=site_hrn, gid=auth_info.get_gid_object(),
                                               pointer=site['site_id'],
                                               authority=get_authority(site_hrn))
                    site_record.just_created()
                    dbsession.add(site_record)
                    dbsession.commit()
                    self.logger.info("PlImporter: imported authority (site) : %s" % site_record) 
                    self.remember_record (site_record)
                except:
                    # if the site import fails then there is no point in trying to import the
                    # site's child records (node, slices, persons), so skip them.
                    self.logger.log_exc("PlImporter: failed to import site. Skipping child records") 
                    continue 
            else:
                # xxx update the record ...
                pass
            site_record.stale=False
             
            # import node records
            for node_id in site['node_ids']:
                try:
                    node = nodes_by_id[node_id]
                except:
                    self.logger.warning ("PlImporter: cannot find node_id %s - ignored"%node_id)
                    continue 
                site_auth = get_authority(site_hrn)
                site_name = site['login_base']
                node_hrn =  hostname_to_hrn(site_auth, site_name, node['hostname'])
                # xxx this sounds suspicious
                if len(node_hrn) > 64: node_hrn = node_hrn[:64]
                node_record = self.locate_by_type_hrn ( 'node', node_hrn )
                if not node_record:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(node_hrn, 'node')
                        node_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        node_record = RegNode (hrn=node_hrn, gid=node_gid, 
                                               pointer =node['node_id'],
                                               authority=get_authority(node_hrn))
                        node_record.just_created()
                        dbsession.add(node_record)
                        dbsession.commit()
                        self.logger.info("PlImporter: imported node: %s" % node_record)  
                        self.remember_record (node_record)
                    except:
                        self.logger.log_exc("PlImporter: failed to import node") 
                else:
                    # xxx update the record ...
                    pass
                node_record.stale=False

            site_pis=[]
            # import persons
            for person_id in site['person_ids']:
                try:
                    person = persons_by_id[person_id]
                except:
                    self.logger.warning ("PlImporter: cannot locate person_id %s - ignored"%person_id)
                person_hrn = email_to_hrn(site_hrn, person['email'])
                # xxx suspicious again
                if len(person_hrn) > 64: person_hrn = person_hrn[:64]
                person_urn = hrn_to_urn(person_hrn, 'user')

                user_record = self.locate_by_type_hrn ( 'user', person_hrn)

                # return a tuple pubkey (a plc key object) and pkey (a Keypair object)
                def init_person_key (person, plc_keys):
                    pubkey=None
                    if  person['key_ids']:
                        # randomly pick first key in set
                        pubkey = plc_keys[0]
                        try:
                            pkey = convert_public_key(pubkey['key'])
                        except:
                            self.logger.warn('PlImporter: unable to convert public key for %s' % person_hrn)
                            pkey = Keypair(create=True)
                    else:
                        # the user has no keys. Creating a random keypair for the user's gid
                        self.logger.warn("PlImporter: person %s does not have a PL public key"%person_hrn)
                        pkey = Keypair(create=True)
                    return (pubkey, pkey)

                # new person
                try:
                    plc_keys = keys_by_person_id.get(person['person_id'],[])
                    if not user_record:
                        (pubkey,pkey) = init_person_key (person, plc_keys )
                        person_gid = self.auth_hierarchy.create_gid(person_urn, create_uuid(), pkey)
                        person_gid.set_email(person['email'])
                        user_record = RegUser (hrn=person_hrn, gid=person_gid, 
                                                 pointer=person['person_id'], 
                                                 authority=get_authority(person_hrn),
                                                 email=person['email'])
                        if pubkey: 
                            user_record.reg_keys=[RegKey (pubkey['key'], pubkey['key_id'])]
                        else:
                            self.logger.warning("No key found for user %s"%user_record)
                        user_record.just_created()
                        dbsession.add (user_record)
                        dbsession.commit()
                        self.logger.info("PlImporter: imported person: %s" % user_record)
                        self.remember_record ( user_record )
                    else:
                        # update the record ?
                        # if user's primary key has changed then we need to update the 
                        # users gid by forcing an update here
                        sfa_keys = user_record.reg_keys
                        def key_in_list (key,sfa_keys):
                            for reg_key in sfa_keys:
                                if reg_key.key==key['key']: return True
                            return False
                        # is there a new key in myplc ?
                        new_keys=False
                        for key in plc_keys:
                            if not key_in_list (key,sfa_keys):
                                new_keys = True
                        if new_keys:
                            (pubkey,pkey) = init_person_key (person, plc_keys)
                            person_gid = self.auth_hierarchy.create_gid(person_urn, create_uuid(), pkey)
                            if not pubkey:
                                user_record.reg_keys=[]
                            else:
                                user_record.reg_keys=[ RegKey (pubkey['key'], pubkey['key_id'])]
                            self.logger.info("PlImporter: updated person: %s" % user_record)
                    user_record.email = person['email']
                    dbsession.commit()
                    user_record.stale=False
                    # accumulate PIs - PLCAPI has a limitation that when someone has PI role
                    # this is valid for all sites she is in..
                    # PI is coded with role_id==20
                    if 20 in person['role_ids']:
                        site_pis.append (user_record)
                except:
                    self.logger.log_exc("PlImporter: failed to import person %d %s"%(person['person_id'],person['email']))
    
            # maintain the list of PIs for a given site
            site_record.reg_pis = site_pis

            # import slices
            for slice_id in site['slice_ids']:
                try:
                    slice = slices_by_id[slice_id]
                except:
                    self.logger.warning ("PlImporter: cannot locate slice_id %s - ignored"%slice_id)
                slice_hrn = slicename_to_hrn(interface_hrn, slice['name'])
                slice_record = self.locate_by_type_hrn ('slice', slice_hrn)
                if not slice_record:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(slice_hrn, 'slice')
                        slice_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        slice_record = RegSlice (hrn=slice_hrn, gid=slice_gid, 
                                                 pointer=slice['slice_id'],
                                                 authority=get_authority(slice_hrn))
                        slice_record.just_created()
                        dbsession.add(slice_record)
                        dbsession.commit()
                        self.logger.info("PlImporter: imported slice: %s" % slice_record)  
                        self.remember_record ( slice_record )
                    except:
                        self.logger.log_exc("PlImporter: failed to import slice")
                else:
                    # xxx update the record ...
                    self.logger.warning ("Slice update not yet implemented")
                    pass
                # record current users affiliated with the slice
                slice_record.reg_researchers = \
                    [ self.locate_by_type_pointer ('user',user_id) for user_id in slice['person_ids'] ]
                dbsession.commit()
                slice_record.stale=False

        ### remove stale records
        # special records must be preserved
        system_hrns = [interface_hrn, root_auth, interface_hrn + '.slicemanager']
        for record in all_records: 
            if record.hrn in system_hrns: 
                record.stale=False
            if record.peer_authority:
                record.stale=False
            if ".vini" in interface_hrn and interface_hrn.endswith('vini') and \
                record.hrn.endswith("internet2"):
                record.stale=False

        for record in all_records:
            try:        stale=record.stale
            except:     
                stale=True
                self.logger.warning("stale not found with %s"%record)
            if stale:
                self.logger.info("PlImporter: deleting stale record: %s" % record)
                dbsession.delete(record)
                dbsession.commit()
