
import os

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn

from sfa.trust.gid import create_uuid    
from sfa.trust.certificate import convert_public_key, Keypair

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegSlice, RegNode, RegUser, RegKey

from sfa.nitos.nitosshell import NitosShell    
from sfa.nitos.nitosxrn import hostname_to_hrn, slicename_to_hrn, email_to_hrn, hrn_to_nitos_slicename, username_to_hrn

def _get_site_hrn(interface_hrn, site):
    hrn = ".".join([interface_hrn, site['name']]) 
    return hrn


class NitosImporter:

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
            self.logger.warning ("NitosImporter.remember_record_by_hrn: duplicate (%s,%s)"%tuple)
            return
        self.records_by_type_hrn [ tuple ] = record

    # ditto for pointer hash
    def remember_record_by_pointer (self, record):
        if record.pointer == -1:
            self.logger.warning ("NitosImporter.remember_record_by_pointer: pointer is void")
            return
        tuple = (record.type, record.pointer)
        if tuple in self.records_by_type_pointer:
            self.logger.warning ("NitosImporter.remember_record_by_pointer: duplicate (%s,%s)"%tuple)
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

    def run (self, options):
        config = Config ()
        interface_hrn = config.SFA_INTERFACE_HRN
        root_auth = config.SFA_REGISTRY_ROOT_AUTH
        shell = NitosShell (config)

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

        ######## retrieve NITOS data
        # Get site info
        # retrieve only required stuf
        site = shell.getTestbedInfo()
        sites = [site]
        # create a hash of sites by login_base
#       # sites_by_login_base = dict ( [ ( site['login_base'], site ) for site in sites ] )
        # Get all NITOS users
        users = shell.getUsers() 
        # create a hash of users by user_id
        users_by_id = dict ( [ ( user['user_id'], user) for user in users ] )
        # Get all NITOS public keys
        # accumulate key ids for keys retrieval
#        key_ids = []
#        for person in persons:
#            key_ids.extend(person['key_ids'])
#        keys = shell.GetKeys( {'peer_id': None, 'key_id': key_ids,
#                               'key_type': 'ssh'} )
#        # create a hash of keys by key_id
#        keys_by_id = dict ( [ ( key['key_id'], key ) for key in keys ] ) 
        # create a dict user_id -> [ (nitos)keys ]
        keys_by_user_id = dict ( [ ( user['user_id'], user['keys']) for user in users ] ) 
        # Get all nitos nodes  
        nodes = shell.getNodes({}, [])
        # create hash by node_id
        nodes_by_id = dict ( [ (node['id'], node) for node in nodes ] )
        # Get all nitos slices
        slices = shell.getSlices({}, [])
        # create hash by slice_id
        slices_by_id = dict ( [ (slice['slice_id'], slice) for slice in slices ] )


        # start importing 
        for site in sites:
        #for i in [0]:
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
                                               pointer=0,
                                               authority=get_authority(site_hrn))
                    site_record.just_created()
                    dbsession.add(site_record)
                    dbsession.commit()
                    self.logger.info("NitosImporter: imported authority (site) : %s" % site_record) 
                    self.remember_record (site_record)
                except:
                    # if the site import fails then there is no point in trying to import the
                    # site's child records (node, slices, persons), so skip them.
                    self.logger.log_exc("NitosImporter: failed to import site. Skipping child records") 
                    continue 
            else:
                # xxx update the record ...
                pass
            site_record.stale=False
             
            # import node records
            for node in nodes:
                site_auth = get_authority(site_hrn)
                site_name = site['name']
                node_hrn =  hostname_to_hrn(site_auth, site_name, node['name'])
                # xxx this sounds suspicious
                if len(node_hrn) > 64: node_hrn = node_hrn[:64]
                node_record = self.locate_by_type_hrn ( 'node', node_hrn )
                if not node_record:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(node_hrn, 'node')
                        node_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        node_record = RegNode (hrn=node_hrn, gid=node_gid, 
                                               pointer =node['id'],
                                               authority=get_authority(node_hrn))
                        node_record.just_created()
                        dbsession.add(node_record)
                        dbsession.commit()
                        self.logger.info("NitosImporter: imported node: %s" % node_record)  
                        self.remember_record (node_record)
                    except:
                           self.logger.log_exc("NitosImporter: failed to import node")
                else:
                    # xxx update the record ...
                    pass
                
                node_record.stale=False


            # import users
            for user in users:
                user_hrn = username_to_hrn(interface_hrn, site['name'], user['username'])
                # xxx suspicious again
                if len(user_hrn) > 64: user_hrn = user_hrn[:64]
                user_urn = hrn_to_urn(user_hrn, 'user')

                user_record = self.locate_by_type_hrn ( 'user', user_hrn)

                # return a tuple pubkey (a nitos key object) and pkey (a Keypair object)
                def init_user_key (user):
                    pubkey = None
                    pkey = None
                    if  user['keys']:
                        # randomly pick first key in set
                        for key in user['keys']:
                             pubkey = key
                             try:
                                pkey = convert_public_key(pubkey)
                                break
                             except:
                                continue
                        if not pkey:
                            self.logger.warn('NitosImporter: unable to convert public key for %s' % user_hrn)
                            pkey = Keypair(create=True)
                    else:
                        # the user has no keys. Creating a random keypair for the user's gid
                        self.logger.warn("NitosImporter: user %s does not have a NITOS public key"%user_hrn)
                        pkey = Keypair(create=True)
                    return (pubkey, pkey)

                # new user
                try:
                    if not user_record:
                        (pubkey,pkey) = init_user_key (user)
                        user_gid = self.auth_hierarchy.create_gid(user_urn, create_uuid(), pkey)
                        user_gid.set_email(user['email'])
                        user_record = RegUser (hrn=user_hrn, gid=user_gid, 
                                                 pointer=user['user_id'], 
                                                 authority=get_authority(user_hrn),
                                                 email=user['email'])
                        if pubkey: 
                            user_record.reg_keys=[RegKey (pubkey)]
                        else:
                            self.logger.warning("No key found for user %s"%user_record)
                        user_record.just_created()
                        dbsession.add (user_record)
                        dbsession.commit()
                        self.logger.info("NitosImporter: imported user: %s" % user_record)
                        self.remember_record ( user_record )
                    else:
                        # update the record ?
                        # if user's primary key has changed then we need to update the 
                        # users gid by forcing an update here
                        sfa_keys = user_record.reg_keys
                        def key_in_list (key,sfa_keys):
                            for reg_key in sfa_keys:
                                if reg_key.key==key: return True
                            return False
                        # is there a new key in NITOS ?
                        new_keys=False
                        for key in user['keys']:
                            if not key_in_list (key,sfa_keys):
                                new_keys = True
                        if new_keys:
                            (pubkey,pkey) = init_user_key (user)
                            user_gid = self.auth_hierarchy.create_gid(user_urn, create_uuid(), pkey)
                            if not pubkey:
                                user_record.reg_keys=[]
                            else:
                                user_record.reg_keys=[ RegKey (pubkey)]
                            self.logger.info("NitosImporter: updated user: %s" % user_record)
                    user_record.email = user['email']
                    dbsession.commit()
                    user_record.stale=False
                except:
                    self.logger.log_exc("NitosImporter: failed to import user %s %s"%(user['user_id'],user['email']))
    

            # import slices
            for slice in slices:
                slice_hrn = slicename_to_hrn(interface_hrn, site['name'], slice['slice_name'])
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
                        self.logger.info("NitosImporter: imported slice: %s" % slice_record)  
                        self.remember_record ( slice_record )
                    except:
                        self.logger.log_exc("NitosImporter: failed to import slice")
                else:
                    # xxx update the record ...
                    self.logger.warning ("Slice update not yet implemented")
                    pass
                # record current users affiliated with the slice
                slice_record.reg_researchers = \
                      [ self.locate_by_type_pointer ('user',int(user_id)) for user_id in slice['user_id'] ]
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

        for record in all_records:
            try:        stale=record.stale
            except:     
                stale=True
                self.logger.warning("stale not found with %s"%record)
            if stale:
                self.logger.info("NitosImporter: deleting stale record: %s" % record)
                dbsession.delete(record)
                dbsession.commit()



if __name__ == "__main__":
       from sfa.util.sfalogging import logger
       nitosimporter = NitosImporter("pla.nitos", logger)
       nitosimporter.run(None)
