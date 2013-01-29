import sys

from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_authority, hrn_to_urn

from sfa.senslab.slabdriver import SlabDriver
from sfa.senslab.slabpostgres import SenslabXP, slab_dbsession

from sfa.trust.certificate import Keypair,convert_public_key
from sfa.trust.gid import create_uuid

from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegSlice, RegNode, \
                                                    RegUser, RegKey
from sfa.util.sfalogging import logger

from sqlalchemy.exc import SQLAlchemyError


def _get_site_hrn(site):
    hrn = site['name'] 
    return hrn

class SlabImporter:
    
    def __init__ (self, auth_hierarchy, loc_logger):
        self.auth_hierarchy = auth_hierarchy
        self.logger = loc_logger
        self.logger.setLevelDebug()

    def hostname_to_hrn_escaped(self, root_auth, hostname):
        return '.'.join( [root_auth,Xrn.escape(hostname)] )


    
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
        
        if not slabdriver.db.exists('slab_xp'):
            slabdriver.db.createtable()
            self.logger.info ("SlabImporter.run:  slab_xp table created ")

        #retrieve all existing SFA objects
        all_records = dbsession.query(RegRecord).all()
      
        #create hash by (type,hrn) 
        #used  to know if a given record is already known to SFA 
       
        self.records_by_type_hrn = \
            dict ( [ ( (record.type,record.hrn) , record ) for record in all_records ] )
        print>>sys.stderr,"\r\n SLABIMPORT \t all_records[0] %s all_records[0].email %s \r\n" %(all_records[0].type, all_records[0])
        self.users_rec_by_email = \
            dict ( [ (record.email, record) for record in all_records if record.type == 'user' ] )
            
        # create hash by (type,pointer) 
        self.records_by_type_pointer = \
            dict ( [ ( (str(record.type),record.pointer) , record ) for record in all_records  if record.pointer != -1] )

        # initialize record.stale to True by default, then mark stale=False on the ones that are in use
        for record in all_records: 
            record.stale=True
        
        nodes_listdict  = slabdriver.GetNodes()
        nodes_by_id = dict([(node['node_id'],node) for node in nodes_listdict])
        sites_listdict  = slabdriver.GetSites()
        
        ldap_person_listdict = slabdriver.GetPersons()
        print>>sys.stderr,"\r\n SLABIMPORT \t ldap_person_listdict %s \r\n" %(ldap_person_listdict)
        slices_listdict = slabdriver.GetSlices()
        try:
            slices_by_userid = dict ( [ (one_slice['reg_researchers']['record_id'], one_slice ) for one_slice in slices_listdict ] )
        except TypeError:
             self.logger.log_exc("SlabImporter: failed to create list of slices by user id.") 
             pass
 
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
                except SQLAlchemyError:
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
                site_name = site['name']                
                escaped_hrn =  self.hostname_to_hrn_escaped(slabdriver.root_auth, node['hostname'])
                print>>sys.stderr, "\r\n \r\n SLABIMPORTER node %s " %(node)               
                hrn =  node['hrn']


                # xxx this sounds suspicious
                if len(hrn) > 64: hrn = hrn[:64]
                node_record = self.find_record_by_type_hrn( 'node', hrn )
                if not node_record:
                    try:
                        pkey = Keypair(create=True)
                        urn = hrn_to_urn(escaped_hrn, 'node') 
                        node_gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
                        def slab_get_authority(hrn):
                            return hrn.split(".")[0]
                            
                        node_record = RegNode (hrn=hrn, gid=node_gid, 
                                                pointer = '-1',
                                                authority=slab_get_authority(hrn)) 
                        node_record.just_created()
                        dbsession.add(node_record)
                        dbsession.commit()
                        #self.logger.info("SlabImporter: imported node: %s" % node_record)  
                        self.update_just_added_records_dict(node_record)
                    except:
                        self.logger.log_exc("SlabImporter: failed to import node") 
                else:
                    # xxx update the record ...
                    pass
                node_record.stale=False
                    
                    
        # import persons
        for person in ldap_person_listdict : 
            

            print>>sys.stderr,"SlabImporter: person: %s" %(person['hrn'])
            if 'ssh-rsa' not in person['pkey']:
                #people with invalid ssh key (ssh-dss, empty, bullshit keys...)
                #won't be imported
                continue
            person_hrn = person['hrn']
            slice_hrn = self.slicename_to_hrn(person['hrn'])
            
            # xxx suspicious again
            if len(person_hrn) > 64: person_hrn = person_hrn[:64]
            person_urn = hrn_to_urn(person_hrn, 'user')
            
            
            print>>sys.stderr," \r\n SlabImporter:  HEYYYYYYYYYY" , self.users_rec_by_email
            
            #Check if user using person['email'] form LDAP is already registered
            #in SFA. One email = one person. Inb this case, do not create another
            #record for this person
            #person_hrn  returned by GetPErson based on senslab root auth + uid ldap
            user_record = self.find_record_by_type_hrn('user', person_hrn)
            if not user_record and  person['email'] in self.users_rec_by_email:
                user_record = self.users_rec_by_email[person['email']]
                person_hrn = user_record.hrn
                person_urn = hrn_to_urn(person_hrn, 'user')
                
            
            slice_record = self.find_record_by_type_hrn ('slice', slice_hrn)
            
            # return a tuple pubkey (a plc key object) and pkey (a Keypair object)
            def init_person_key (person, slab_key):
                pubkey = None
                if  person['pkey']:
                    # randomly pick first key in set
                    pubkey = slab_key
                    
                    try:
                        pkey = convert_public_key(pubkey)
                    except TypeError:
                        #key not good. create another pkey
                        self.logger.warn('SlabImporter: \
                                            unable to convert public \
                                            key for %s' % person_hrn)
                        pkey = Keypair(create=True)
                    
                else:
                    # the user has no keys. Creating a random keypair for the user's gid
                    self.logger.warn("SlabImporter: person %s does not have a  public key"%person_hrn)
                    pkey = Keypair(create=True) 
                return (pubkey, pkey)
                            
                
            try:
                slab_key = person['pkey']
                # new person
                if not user_record:
                    (pubkey,pkey) = init_person_key (person, slab_key )
                    if pubkey is not None and pkey is not None :
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
                            user_record.reg_keys = [RegKey (pubkey)]
                        else:
                            self.logger.warning("No key found for user %s"%user_record)
                        user_record.just_created()
                        dbsession.add (user_record)
                        dbsession.commit()
                        self.logger.info("SlabImporter: imported person: %s" % user_record)
                        self.update_just_added_records_dict( user_record )
                else:
                    # update the record ?
                    # if user's primary key has changed then we need to update the 
                    # users gid by forcing an update here
                    sfa_keys = user_record.reg_keys
                   
                    new_key=False
                    if slab_key is not sfa_keys : 
                        new_key = True
                    if new_key:
                        print>>sys.stderr,"SlabImporter: \t \t USER UPDATE person: %s" %(person['hrn'])
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

                user_record.stale = False
            except:
                self.logger.log_exc("SlabImporter: failed to import person  %s"%(person) )       
            
            try:
                slice = slices_by_userid[user_record.record_id]
            except:
                self.logger.warning ("SlabImporter: cannot locate slices_by_userid[user_record.record_id] %s - ignored"%user_record)  
                    
            if not slice_record :
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
                    
                    #slab_slice = SenslabXP( slice_hrn = slice_hrn, record_id_slice=sl_rec[0].record_id, record_id_user= user_record.record_id)
                    #print>>sys.stderr, "\r\n \r\n SLAB IMPORTER SLICE IMPORT NOTslice_record %s \r\n slab_slice %s" %(sl_rec,slab_slice)
                    #slab_dbsession.add(slab_slice)
                    #slab_dbsession.commit()
                    #self.logger.info("SlabImporter: imported slice: %s" % slice_record)  
                    self.update_just_added_records_dict ( slice_record )

                except:
                    self.logger.log_exc("SlabImporter: failed to import slice")
                    
            #No slice update upon import in senslab 
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
            if record.type == 'user':
                print>>sys.stderr,"SlabImporter: stale records: hrn %s %s" %(record.hrn,record.stale)
            try:        
                stale=record.stale
            except:     
                stale=True
                self.logger.warning("stale not found with %s"%record)
            if stale:
                self.logger.info("SlabImporter: deleting stale record: %s" % record)
                #if record.type == 'user':
                    #rec = slab_dbsession.query(SenslabXP).filter_by(record_id_user = record.record_id).first()
                    #slab_dbsession.delete(rec)
                    #slab_dbsession.commit()
                dbsession.delete(record)
                dbsession.commit()         
                 

  
