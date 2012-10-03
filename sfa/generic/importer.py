import os

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn

from sfa.trust.gid import create_uuid    
from sfa.trust.certificate import convert_public_key, Keypair

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegSlice, RegNode, RegUser, RegKey

class Importer:

    def __init__ (self, auth_hierarchy, logger):
        self.auth_hierarchy = auth_hierarchy
        self.logger=logger

    def add_options (self, parser):
        # We don't have any options for now
        pass

    # hrn hash is initialized from current db
    # remember just-created records as we go
    # xxx might make sense to add a UNIQUE constraint in the db itself
    def remember_record_by_hrn (self, record):
        tuple = (record.type, record.hrn)
        if tuple in self.records_by_type_hrn:
            self.logger.warning ("Importer.remember_record_by_hrn: duplicate (%s,%s)"%tuple)
            return
        self.records_by_type_hrn [ tuple ] = record

    # ditto for pointer hash
    def remember_record_by_pointer (self, record):
        if record.pointer == -1:
            self.logger.warning ("Importer.remember_record_by_pointer: pointer is void")
            return
        tuple = (record.type, record.pointer)
        if tuple in self.records_by_type_pointer:
            self.logger.warning ("Importer.remember_record_by_pointer: duplicate (%s,%s)"%tuple)
            return
        self.records_by_type_pointer [ ( record.type, record.pointer,) ] = record

    def remember_record (self, record):
        self.remember_record_by_hrn (record)
        self.remember_record_by_pointer (record)

    def locate_by_type_hrn (self, type, hrn):
        return self.records_by_type_hrn.get ( (type, hrn), None)

    def locate_by_type_pointer (self, type, pointer):
        return self.records_by_type_pointer.get ( (type, pointer), None)

    ############################################################################
    # Object import functions (authorities, resources, users, slices)
    #

    def import_auth(self, auth, parent_auth_hrn):
        """
        @return HRN of the newly created authority
        """
        auth_hrn = self.get_auth_naming(auth, parent_auth_hrn)
        auth_urn = hrn_to_urn(auth_hrn, 'authority')

        # import if hrn is not in list of existing hrns or if the hrn exists
        # but its not a auth record
        auth_record=self.locate_by_type_hrn ('authority', auth_hrn)
        if not auth_record:
            try:
                # We ensure the parent is created through the root
                #if not self.auth_hierarchy.auth_exists(auth_urn):
                #    self.auth_hierarchy.create_auth(auth_urn)
                auth_info = self.auth_hierarchy.get_auth_info(auth_urn)
                auth_record = RegAuthority(hrn = auth_hrn, gid = auth_info.get_gid_object(),
                                           pointer = 0,
                                           authority = get_authority(auth_hrn))
                auth_record.just_created()
                dbsession.add(auth_record)
                dbsession.commit()
                self.logger.info("Importer: imported authority (auth) : %s" % auth_record) 
                self.remember_record (auth_record)
            except Exception, e:
                # if the auth import fails then there is no point in trying to import the
                # auth's child records (node, slices, persons), so skip them.
                raise Exception, "Importer: failed to import auth. Skipping child records : %s" % e
        else:
            # xxx update the record ...
            pass
        auth_record.stale=False

        return auth_hrn

    def import_resource(self, resource, parent_auth_hrn):
        """
        @return HRN of the newly created resource
        """
        resource_hrn = self.get_resource_naming(resource, parent_auth_hrn)
        resource_urn = hrn_to_urn(resource_hrn, 'node')

        resource_record = self.locate_by_type_hrn ('node', resource_hrn )
        if not resource_record:
            try:
                pkey = Keypair(create=True)
                resource_gid = self.auth_hierarchy.create_gid(resource_urn, create_uuid(), pkey)
                resource_record = RegNode (hrn = resource_hrn, gid = resource_gid, 
                                       pointer = resource['id'],
                                       authority = get_authority(resource_hrn))
                resource_record.just_created()
                dbsession.add(resource_record)
                dbsession.commit()
                self.logger.info("Importer: imported resource: %s" % resource_record)  
                self.remember_record (resource_record)
            except:
                   self.logger.log_exc("Importer: failed to import resource")
        else:
            # xxx update the record ...
            pass
        
        resource_record.stale=False

        return resource_hrn

    def init_user_key(self, user):
        pubkey = None
        pkey = None
        if user['keys']:
            # pick first working key in set
            for pubkey in user['keys']:
                 try:
                    pkey = convert_public_key(pubkey)
                    break
                 except:
                    continue
            if not pkey:
                self.logger.warn('Importer: unable to convert public key for %s' % user_hrn)
                pkey = Keypair(create=True)
        else:
            # the user has no keys. Creating a random keypair for the user's gid
            self.logger.warn("Importer: user %s does not have a public key on the testbed"%user_hrn)
            pkey = Keypair(create=True)
        return (pubkey, pkey)

    def import_user(self, user, parent_auth_hrn):
        """
        @return HRN of the newly created user
        """
        user_hrn = self.get_user_naming(user, parent_auth_hrn)
        user_urn = hrn_to_urn(user_hrn, 'user')

        # return a tuple pubkey (a public key) and pkey (a Keypair object)

        user_record = self.locate_by_type_hrn ( 'user', user_hrn)
        try:
            if not user_record:
                (pubkey,pkey) = self.init_user_key (user)
                user_gid = self.auth_hierarchy.create_gid(user_urn, create_uuid(), pkey)
                user_gid.set_email(user['email'])
                user_record = RegUser(hrn = user_hrn, gid = user_gid, 
                                         pointer = user['id'], 
                                         authority = get_authority(user_hrn),
                                         email = user['email'])
                if pubkey: 
                    user_record.reg_keys=[RegKey(pubkey)]
                else:
                    self.logger.warning("No key found for user %s" % user_record)
                user_record.just_created()
                dbsession.add (user_record)
                dbsession.commit()
                self.logger.info("Importer: imported user: %s" % user_record)
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
                # is there a new key ? XXX understand ?
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
                    self.logger.info("Importer: updated user: %s" % user_record)
            user_record.email = user['email']
            dbsession.commit()
            user_record.stale=False
        except:
            self.logger.log_exc("Importer: failed to import user %s %s"%(user['id'],user['email']))

        return user_hrn

    def import_slice(self, slice, parent_auth_hrn):
        """
        @return HRN of the newly created slice
        """
        slice_hrn = self.get_slice_naming(slice, parent_auth_hrn)
        slice_urn = hrn_to_urn(slice_hrn, 'slice')

        slice_record = self.locate_by_type_hrn ('slice', slice_hrn)
        if not slice_record:
            try:
                pkey = Keypair(create=True)
                slice_gid = self.auth_hierarchy.create_gid(slice_urn, create_uuid(), pkey)
                slice_record = RegSlice (hrn=slice_hrn, gid=slice_gid, 
                                         pointer=slice['id'],
                                         authority=get_authority(slice_hrn))
                slice_record.just_created()
                dbsession.add(slice_record)
                dbsession.commit()
                self.logger.info("Importer: imported slice: %s" % slice_record)  
                self.remember_record ( slice_record )
            except:
                self.logger.log_exc("Importer: failed to import slice")
        else:
            # xxx update the record ...
            self.logger.warning ("Slice update not yet implemented")
            pass
        # record current users affiliated with the slice
        slice_record.reg_researchers = \
              [ self.locate_by_type_pointer ('user',int(id)) for id in slice['user_ids'] ]
        dbsession.commit()
        slice_record.stale=False

        return slice_hrn

    ############################################################################
    # Recursive import
    #
    def import_auth_rec(self, auth, parent=None):
        """
        Import authority and related objects (resources, users, slices), then
        recurse through all subauthorities.

        @param auth authority to be processed.
        @return 1 if successful, exception otherwise
        """

        # Create entry for current authority
        try:
            auth_hrn = self.import_auth(auth, parent)

            # Import objects related to current authority
            if auth['resource_ids']:
                for resource_id in auth['resource_ids']:
                    self.import_resource(self.resources_by_id[resource_id], auth_hrn)
            if auth['user_ids']:
                for user_id in auth['user_ids']:
                    self.import_user(self.users_by_id[user_id], auth_hrn)
            if auth['slice_ids']:
                for slice_id in auth['slice_ids']:
                    self.import_slice(self.slices_by_id[slice_id], auth_hrn)

            # Recursive import of subauthorities
            if auth['auth_ids']:
                for auth_id in auth['auth_ids']:
                    self.import_auth_rec(self.authorities_by_id[auth_id], auth_hrn)
        except Exception, e:
            self.logger.log_exc(e)
            pass

    def locate_by_type_hrn (self, type, hrn):
        return self.records_by_type_hrn.get ( (type, hrn), None)

    ############################################################################
    # Main processing function
    #
    def run (self, options):
        config = Config ()
        interface_hrn = config.SFA_INTERFACE_HRN
        root_auth = config.SFA_REGISTRY_ROOT_AUTH
        # <mytestbed> shell = NitosShell (config)

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

        ######## Data collection

    	# Here we make the adaptation between the testbed API, and dictionaries with required fields

        # AUTHORITIES
        authorities = self.get_authorities()
        self.authorities_by_id = {}
        if authorities:
            self.authorities_by_id = dict([(auth['id'], auth) for auth in authorities])

        # USERS & KEYS
        users = self.get_users()
        self.users_by_id = {}
        self.keys_by_id = {}
        if users:
            self.users_by_id = dict ( [ ( user['id'], user) for user in users ] )
            self.keys_by_id = dict ( [ ( user['id'], user['keys']) for user in users ] ) 

        # RESOURCES
        resources = self.get_resources()
        self.resources_by_id = {}
        if resources:
            self.resources_by_id = dict ( [ (resource['id'], resource) for resource in resources ] )

        # SLICES
        slices = self.get_slices()
        self.slices_by_id = {}
        if slices:
            self.slices_by_id = dict ( [ (slice['id'], slice) for slice in slices ] )

        ######## Import process

        if authorities:
            # Everybody belongs to sub-authorities, and we rely on the different
            # subauthorities to give appropriate pointers to objects.
            root = {
                'id': 0,
                'name': interface_hrn,
                'auth_ids': self.authorities_by_id.keys(),
                'user_ids': None,
                'resource_ids': None,
                'slice_ids': None
            }
        else:
            # We create a root authority with all objects linked to it.
            root = {
                'id': 0,
                'name': interface_hrn,
                'auth_ids': self.authorities_by_id.keys(),
                'user_ids': self.users_by_id.keys(),
                'resource_ids': self.resources_by_id.keys(),
                'slice_ids': self.slices_by_id.keys()
            }

        # Recurse through authorities and import the different objects
        self.import_auth_rec(root)

        ######## Remove stale records

        # special records must be preserved
        system_hrns = [interface_hrn, root_auth, interface_hrn + '.slicemanager']
        for record in all_records: 
            if record.hrn in system_hrns: 
                record.stale=False
            if record.peer_authority:
                record.stale=False

        for record in all_records:
            try:
                stale = record.stale
            except:     
                stale = True
                self.logger.warning("stale not found with %s"%record)
            if stale:
                self.logger.info("Importer: deleting stale record: %s" % record)
                dbsession.delete(record)
                dbsession.commit()

    ############################################################################ 
    # Testbed specific functions

    # OBJECTS

    def get_authorities(self):
        raise Exception, "Not implemented"

    def get_resources(self):
        raise Exception, "Not implemented"

    def get_users(self):
        raise Exception, "Not implemented"

    def get_slices(self):
        raise Exception, "Not implemented"

    # NAMING
    
    def get_auth_naming(self, site, interface_hrn):
        raise Exception, "Not implemented"

    def get_resource_naming(self, site, node):
        raise Exception, "Not implemented"

    def get_user_naming(self, site, user):
        raise Exception, "Not implemented"

    def get_slice_naming(self, site, slice):
        raise Exception, "Not implemented"

if __name__ == "__main__":
       from sfa.util.sfalogging import logger
       importer = Importer("mytestbed", logger)
       importer.run(None)
