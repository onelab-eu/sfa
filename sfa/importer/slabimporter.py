import os
import sys
import datetime
import time

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn
from sfa.util.plxrn import PlXrn, slicename_to_hrn, email_to_hrn, hrn_to_pl_slicename

from sfa.senslab.LDAPapi import LDAPapi
from sfa.senslab.slabdriver import SlabDriver
from sfa.senslab.slabpostgres import SlabSliceDB, slab_dbsession

from sfa.trust.certificate import Keypair,convert_public_key
from sfa.trust.gid import create_uuid

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegSlice, RegNode, RegUser, RegKey
from sfa.storage.dbschema import DBSchema



def _get_site_hrn(site):
    hrn = site['login_base'] 
    return hrn

class SlabImporter:
    
    def __init__ (self, auth_hierarchy, logger):
        self.auth_hierarchy = auth_hierarchy
        self.logger=logger

       
    def hostname_to_hrn(self,root_auth,login_base,hostname):
        return PlXrn(auth=root_auth,hostname=login_base+'_'+hostname).get_hrn()   
    
    def slicename_to_hrn(self, person_hrn):
        return  (person_hrn +'_slice')
    
    def add_options (self, parser):
        # we don't have any options for now
        pass
    
    def find_record_by_type_hrn(self,type,hrn):
        return self.records_by_type_hrn.get ( (type, hrn), None)
    
    def locate_by_type_pointer (self, type, pointer):
        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES locate_by_type_pointer  .........................." 
        ret = self.records_by_type_pointer.get ( (type, pointer), None)
        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES locate_by_type_pointer  " 
        return ret
    
    def update_just_added_records_dict (self, record):
        tuple = (record.type, record.hrn)
        if tuple in self.records_by_type_hrn:
            self.logger.warning ("SlabImporter.update_just_added_records_dict: duplicate (%s,%s)"%tuple)
            return
        self.records_by_type_hrn [ tuple ] = record
        
    def run (self, options):
        config = Config()

        slabdriver = SlabDriver(config)
        
        #Create special slice table for senslab 
        
        if not slabdriver.db.exists('slice_senslab'):
            slabdriver.db.createtable('slice_senslab')
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES CREATETABLE  YAAAAAAAAAAY"        
       ######## retrieve all existing SFA objects
        all_records = dbsession.query(RegRecord).all()
        #print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES all_records %s" %(all_records)
        #create hash by (type,hrn) 
        #used  to know if a given record is already known to SFA 
       
        self.records_by_type_hrn = \
            dict ( [ ( (record.type,record.hrn) , record ) for record in all_records ] )
            
        # create hash by (type,pointer) 
        self.records_by_type_pointer = \
            dict ( [ ( (str(record.type),record.pointer) , record ) for record in all_records  if record.pointer != -1] )
        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES   self.records_by_type_pointer  %s" %(  self.records_by_type_pointer)
        # initialize record.stale to True by default, then mark stale=False on the ones that are in use
        for record in all_records: 
            record.stale=True
        
        nodes_listdict  = slabdriver.GetNodes()
        nodes_by_id = dict([(node['node_id'],node) for node in nodes_listdict])
        sites_listdict  = slabdriver.GetSites()
        
        ldap_person_listdict = slabdriver.GetPersons()
        slices_listdict = slabdriver.GetSlices()
        try:
            slices_by_userid = dict ( [ (slice.record_id_user, slice ) for slice in slices_listdict ] )
        except TypeError:
             print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES  slices_listdict EMPTY "
             pass
        #print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES  slices_by_userid   %s" %( slices_by_userid)
        for site in sites_listdict:
            site_hrn = _get_site_hrn(site) 
            site_record = self.find_record_by_type_hrn ('authority', site_hrn)
            if not site_record:
                try:
                    urn = hrn_to_urn(site_hrn, 'authority')
                    if not self.auth_hierarchy.auth_exists(urn):
                        self.auth_hierarchy.create_auth(urn)
                    auth_info = self.auth_hierarchy.get_auth_info(urn)
                    site_record = RegAuthority(hrn=site_hrn, gid=auth_info.get_gid_object(),
                                               pointer='-1',
                                               authority=get_authority(site_hrn))
                    site_record.just_created()
                    dbsession.add(site_record)
                    dbsession.commit()
                    self.logger.info("SlabImporter: imported authority (site) : %s" % site_record) 
                    self.update_just_added_records_dict(site_record)
                except:
                    # if the site import fails then there is no point in trying to import the
                    # site's child records (node, slices, persons), so skip them.
                    self.logger.log_exc("SlabImporter: failed to import site. Skipping child records") 
                    continue
            else:
                # xxx update the record ...
                pass
            site_record.stale=False 
            
         # import node records in site
            for node_id in site['node_ids']:
                try:
                    node = nodes_by_id[node_id]
                except:
                    self.logger.warning ("SlabImporter: cannot find node_id %s - ignored"%node_id)
                    continue 
                site_auth = get_authority(site_hrn)
                site_name = site['login_base']
                hrn =  self.hostname_to_hrn(slabdriver.root_auth, site_name, node['hostname'])
                # xxx this sounds suspicious
                if len(hrn) > 64: hrn = hrn[:64]
                node_record = self.find_record_by_type_hrn( 'node', hrn )
                #print >>sys.stderr, " \r\n \r\n SLAB IMPORTER node_record %s " %(node_record)
                if not node_record:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(hrn, 'node') 
                        #print>>sys.stderr, "\r\n \r\n SLAB IMPORTER NODE IMPORT urn %s hrn %s" %(urn, hrn)  
                        node_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        node_record = RegNode (hrn=hrn, gid=node_gid, 
                                                pointer =node['node_id'],
                                                authority=get_authority(hrn))
                        node_record.just_created()
                        dbsession.add(node_record)
                        dbsession.commit()
                        self.logger.info("SlabImporter: imported node: %s" % node_record)
                        print>>sys.stderr, "\r\n \t\t\t SLAB IMPORTER NODE IMPORT NOTnode_record %s " %(node_record)  
                        self.update_just_added_records_dict(node_record)
                    except:
                        self.logger.log_exc("SlabImporter: failed to import node") 
                else:
                    # xxx update the record ...
                    pass
                node_record.stale=False
                    
                    
            # import persons
            for person in ldap_person_listdict : 
            
                person_hrn = person['hrn']
                slice_hrn = self.slicename_to_hrn(person['hrn'])
               
                # xxx suspicious again
                if len(person_hrn) > 64: person_hrn = person_hrn[:64]
                person_urn = hrn_to_urn(person_hrn, 'user')
    
                user_record = self.find_record_by_type_hrn( 'user', person_hrn)
                slice_record = self.find_record_by_type_hrn ('slice', slice_hrn)
                print>>sys.stderr, "\r\n \r\n SLAB IMPORTER FROM LDAP LIST PERSON IMPORT user_record %s " %(user_record)
                
                
                # return a tuple pubkey (a plc key object) and pkey (a Keypair object)
                def init_person_key (person, slab_key):
                    pubkey=None
                    if  person['pkey']:
                        # randomly pick first key in set
                        pubkey = slab_key
                        try:
                            pkey = convert_public_key(pubkey)
                        except:
                            self.logger.warn('SlabImporter: unable to convert public key for %s' % person_hrn)
                            pkey = Keypair(create=True)
                    else:
                        # the user has no keys. Creating a random keypair for the user's gid
                        self.logger.warn("SlabImporter: person %s does not have a PL public key"%person_hrn)
                        pkey = Keypair(create=True)
                    return (pubkey, pkey)
                                
                 
                try:
                    slab_key = person['pkey']
                    # new person
                    if not user_record:
                        (pubkey,pkey) = init_person_key (person, slab_key )
                        person_gid = self.auth_hierarchy.create_gid(person_urn, create_uuid(), pkey)
                        if person['email']:
                            print>>sys.stderr, "\r\n \r\n SLAB IMPORTER PERSON EMAIL OK email %s " %(person['email'])
                            person_gid.set_email(person['email'])
                            user_record = RegUser (hrn=person_hrn, gid=person_gid, 
                                                    pointer='-1', 
                                                    authority=get_authority(person_hrn),
                                                    email=person['email'])
                        else:
                            user_record = RegUser (hrn=person_hrn, gid=person_gid, 
                                                    pointer='-1', 
                                                    authority=get_authority(person_hrn))
                            
                        if pubkey: 
                            user_record.reg_keys=[RegKey (pubkey)]
                        else:
                            self.logger.warning("No key found for user %s"%user_record)
                        user_record.just_created()
                        dbsession.add (user_record)
                        dbsession.commit()
                        self.logger.info("SlabImporter: imported person: %s" % user_record)
                        print>>sys.stderr, "\r\n \r\n SLAB IMPORTER PERSON IMPORT NOTuser_record %s " %(user_record)
                        self.update_just_added_records_dict( user_record )
                    else:
                        # update the record ?
                        # if user's primary key has changed then we need to update the 
                        # users gid by forcing an update here
                        sfa_keys = user_record.reg_keys
                        #def key_in_list (key,sfa_keys):
                            #for reg_key in sfa_keys:
                                #if reg_key.key==key['key']: return True
                            #return False
                        # is there a new key in myplc ?
                        new_keys=False
                        if slab_key is not sfa_keys : 
                            new_keys = True
                        if new_keys:
                            (pubkey,pkey) = init_person_key (person, slab_key)
                            person_gid = self.auth_hierarchy.create_gid(person_urn, create_uuid(), pkey)
                            if not pubkey:
                                user_record.reg_keys=[]
                            else:
                                user_record.reg_keys=[ RegKey (pubkey)]
                            self.logger.info("SlabImporter: updated person: %s" % user_record)
                    if person['email']:
                        user_record.email = person['email']
                    dbsession.commit()
                    user_record.stale=False
                except:
                    self.logger.log_exc("SlabImporter: failed to import person  %s"%(person) )       
                
                try:
                    slice = slices_by_userid[user_record.record_id]
                except:
                    self.logger.warning ("SlabImporter: cannot locate slices_by_userid[user_record.record_id] %s - ignored"%user_record.record_id )    
                if not slice_record:
                   
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(slice_hrn, 'slice')
                        slice_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        slice_record = RegSlice (hrn=slice_hrn, gid=slice_gid, 
                                                    pointer='-1',
                                                    authority=get_authority(slice_hrn))
                     
                        slice_record.just_created()
                        dbsession.add(slice_record)
                        dbsession.commit()
                        
                        #Serial id created after commit
                        #Get it
                        sl_rec = dbsession.query(RegSlice).filter(RegSlice.hrn.match(slice_hrn)).all()
                        
                        slab_slice = SlabSliceDB( slice_hrn = slice_hrn,  record_id_slice=sl_rec[0].record_id, record_id_user= user_record.record_id)
                        print>>sys.stderr, "\r\n \r\n SLAB IMPORTER SLICE IMPORT NOTslice_record %s \r\n slab_slice %s" %(sl_rec,slab_slice)
                        slab_dbsession.add(slab_slice)
                        slab_dbsession.commit()
                        self.logger.info("SlabImporter: imported slice: %s" % slice_record)  
                        self.update_just_added_records_dict ( slice_record )
                    except:
                        self.logger.log_exc("SlabImporter: failed to import slice")
                else:
                    # xxx update the record ...
                    self.logger.warning ("Slice update not yet implemented")
                    pass
                # record current users affiliated with the slice

                slice_record.reg_researchers =  [user_record]
                dbsession.commit()
                slice_record.stale=False 
                       
  
                 
         ### remove stale records
        # special records must be preserved
        system_hrns = [slabdriver.hrn, slabdriver.root_auth,  slabdriver.hrn+ '.slicemanager']
        for record in all_records: 
            if record.hrn in system_hrns: 
                record.stale=False
            if record.peer_authority:
                record.stale=False
          

        for record in all_records:
            try:        
                stale=record.stale
            except:     
                stale=True
                self.logger.warning("stale not found with %s"%record)
            if stale:
                self.logger.info("SlabImporter: deleting stale record: %s" % record)
                dbsession.delete(record)
                dbsession.commit()         
                 

  