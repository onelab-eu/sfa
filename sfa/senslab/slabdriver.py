import os

from datetime import datetime

from sfa.util.faults import SliverDoesNotExist, UnknownSfaType
from sfa.util.sfalogging import logger
from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord, RegUser, RegSlice, RegKey
from sqlalchemy.orm import joinedload

from sfa.trust.certificate import Keypair, convert_public_key
from sfa.trust.gid import create_uuid
from sfa.trust.hierarchy import Hierarchy

from sfa.managers.driver import Driver
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.util.xrn import Xrn, hrn_to_urn, get_authority

from sfa.senslab.OARrestapi import  OARrestapi
from sfa.senslab.LDAPapi import LDAPapi

from sfa.senslab.slabpostgres import SlabDB, slab_dbsession, SenslabXP
                                                     
                                                                
from sfa.senslab.slabaggregate import SlabAggregate, slab_xrn_to_hostname, \
                                                            slab_xrn_object
from sfa.senslab.slabslices import SlabSlices


from sfa.senslab.slabapi import SlabTestbedAPI


     
class SlabDriver(Driver):
    """ Senslab Driver class inherited from Driver generic class.
    
    Contains methods compliant with the SFA standard and the testbed
    infrastructure (calls to LDAP and OAR).
    """
    def __init__(self, config):
        Driver.__init__ (self, config)
        self.config = config
        self.hrn = config.SFA_INTERFACE_HRN

        self.db = SlabDB(config, debug = False)
        self.slab_api = SlabTestbedAPI(config)
        self.cache = None
        
    def augment_records_with_testbed_info (self, record_list ):
        """ Adds specific testbed info to the records. """
        return self.fill_record_info (record_list)
    
    def fill_record_info(self, record_list):
        """
        Given a SFA record, fill in the senslab specific and SFA specific
        fields in the record. 
        """
                    
        logger.debug("SLABDRIVER \tfill_record_info records %s " %(record_list))
        if not isinstance(record_list, list):
            record_list = [record_list]
            
        try:
            for record in record_list:
                #If the record is a SFA slice record, then add information 
                #about the user of this slice. This kind of 
                #information is in the Senslab's DB.
                if str(record['type']) == 'slice':
                    if 'reg_researchers' in record and \
                    isinstance(record['reg_researchers'], list) :
                        record['reg_researchers'] = record['reg_researchers'][0].__dict__
                        record.update({'PI':[record['reg_researchers']['hrn']],
                                'researcher': [record['reg_researchers']['hrn']],
                                'name':record['hrn'], 
                                'oar_job_id':[],
                                'node_ids': [],
                                'person_ids':[record['reg_researchers']['record_id']],
                                'geni_urn':'',  #For client_helper.py compatibility
                                'keys':'',  #For client_helper.py compatibility
                                'key_ids':''})  #For client_helper.py compatibility
                        
                        
                    #Get slab slice record and oar job id if any.
                    recslice_list = self.slab_api.GetSlices(slice_filter = \
                                                str(record['hrn']),\
                                                slice_filter_type = 'slice_hrn')
                    
                   
                    logger.debug("SLABDRIVER \tfill_record_info \
                        TYPE SLICE RECUSER record['hrn'] %s ecord['oar_job_id']\
                         %s " %(record['hrn'], record['oar_job_id']))
                    try:
                        for rec in recslice_list: 
                            logger.debug("SLABDRIVER\r\n  \t  fill_record_info oar_job_id %s " %(rec['oar_job_id']))
                            del record['reg_researchers']
                            record['node_ids'] = [ self.slab_api.root_auth + hostname for hostname in rec['node_ids']]
                    except KeyError:
                        pass

                    logger.debug( "SLABDRIVER.PY \t fill_record_info SLICE \
                                    recslice_list  %s \r\n \t RECORD %s \r\n \
                                    \r\n" %(recslice_list, record)) 
                                    
                if str(record['type']) == 'user':
                    #The record is a SFA user record.
                    #Get the information about his slice from Senslab's DB
                    #and add it to the user record.
                    recslice_list = self.slab_api.GetSlices(\
                            slice_filter = record['record_id'],\
                            slice_filter_type = 'record_id_user')
                                            
                    logger.debug( "SLABDRIVER.PY \t fill_record_info TYPE USER \
                                                recslice_list %s \r\n \t RECORD %s \r\n" %(recslice_list , record)) 
                    #Append slice record in records list, 
                    #therefore fetches user and slice info again(one more loop)
                    #Will update PIs and researcher for the slice
                   
                    recuser = recslice_list[0]['reg_researchers']
                    logger.debug( "SLABDRIVER.PY \t fill_record_info USER  \
                                                recuser %s \r\n \r\n" %(recuser)) 
                    recslice = {}
                    recslice = recslice_list[0]
                    recslice.update({'PI':[recuser['hrn']],
                        'researcher': [recuser['hrn']],
                        'name':record['hrn'], 
                        'node_ids': [],
                        'oar_job_id': [],
                        'person_ids':[recuser['record_id']]}) 
                    try:
                        for rec in recslice_list:
                            recslice['oar_job_id'].append(rec['oar_job_id'])
                    except KeyError:
                        pass
                            
                    recslice.update({'type':'slice', \
                                                'hrn':recslice_list[0]['hrn']})


                    #GetPersons takes [] as filters 
                    user_slab = self.slab_api.GetPersons([record])
    
                    
                    record.update(user_slab[0])
                    #For client_helper.py compatibility
                    record.update( { 'geni_urn':'',
                    'keys':'',
                    'key_ids':'' })                
                    record_list.append(recslice)
                    
                    logger.debug("SLABDRIVER.PY \tfill_record_info ADDING SLICE\
                                INFO TO USER records %s" %(record_list)) 
                  

        except TypeError, error:
            logger.log_exc("SLABDRIVER \t fill_record_info  EXCEPTION %s"\
                                                                     %(error))
                              
        return
                    
                    
    def sliver_status(self, slice_urn, slice_hrn):
        """Receive a status request for slice named urn/hrn 
        urn:publicid:IDN+senslab+nturro_slice hrn senslab.nturro_slice
        shall return a structure as described in
        http://groups.geni.net/geni/wiki/GAPI_AM_API_V2#SliverStatus
        NT : not sure if we should implement this or not, but used by sface.
        
        """
        
        #First get the slice with the slice hrn
        slice_list =  self.slab_api.GetSlices(slice_filter = slice_hrn, \
                                    slice_filter_type = 'slice_hrn')
        
        if len(slice_list) is 0:
            raise SliverDoesNotExist("%s  slice_hrn" % (slice_hrn))
        
        #Used for fetching the user info witch comes along the slice info 
        one_slice = slice_list[0] 

        
        #Make a list of all the nodes hostnames  in use for this slice
        slice_nodes_list = []
        #for single_slice in slice_list:
            #for node in single_slice['node_ids']:
                #slice_nodes_list.append(node['hostname'])
        for node in one_slice:
            slice_nodes_list.append(node['hostname'])
            
        #Get all the corresponding nodes details    
        nodes_all = self.slab_api.GetNodes({'hostname':slice_nodes_list},
                                ['node_id', 'hostname','site','boot_state'])
        nodeall_byhostname = dict([(one_node['hostname'], one_node) \
                                            for one_node in nodes_all])  
          
          
          
        for single_slice in slice_list:

              #For compatibility
            top_level_status = 'empty' 
            result = {}
            result.fromkeys(\
                ['geni_urn','pl_login','geni_status','geni_resources'], None)
            result['pl_login'] = one_slice['reg_researchers']['hrn']
            logger.debug("Slabdriver - sliver_status Sliver status \
                                        urn %s hrn %s single_slice  %s \r\n " \
                                        %(slice_urn, slice_hrn, single_slice))
                                        
            if 'node_ids' not in single_slice:
                #No job in the slice
                result['geni_status'] = top_level_status
                result['geni_resources'] = [] 
                return result
           
            top_level_status = 'ready' 

            #A job is running on Senslab for this slice
            # report about the local nodes that are in the slice only
         
            result['geni_urn'] = slice_urn

            resources = []
            for node in single_slice['node_ids']:
                res = {}
                #res['slab_hostname'] = node['hostname']
                #res['slab_boot_state'] = node['boot_state']
                
                res['pl_hostname'] = node['hostname']
                res['pl_boot_state'] = \
                            nodeall_byhostname[node['hostname']]['boot_state']
                #res['pl_last_contact'] = strftime(self.time_format, \
                                                    #gmtime(float(timestamp)))
                sliver_id =  Xrn(slice_urn, type='slice', \
                        id=nodeall_byhostname[node['hostname']]['node_id'], \
                        authority=self.hrn).urn
    
                res['geni_urn'] = sliver_id 
                node_name  = node['hostname']
                if nodeall_byhostname[node_name]['boot_state'] == 'Alive':

                    res['geni_status'] = 'ready'
                else:
                    res['geni_status'] = 'failed'
                    top_level_status = 'failed' 
                    
                res['geni_error'] = ''
        
                resources.append(res)
                
            result['geni_status'] = top_level_status
            result['geni_resources'] = resources 
            logger.debug("SLABDRIVER \tsliver_statusresources %s res %s "\
                                                    %(resources,res))
            return result  
                
    @staticmethod                
    def get_user_record( hrn):        
        """ Returns the user record based on the hrn from the SFA DB """
        return dbsession.query(RegRecord).filter_by(hrn = hrn).first() 
         
     
    def testbed_name (self): 
        return self.hrn
         
    # 'geni_request_rspec_versions' and 'geni_ad_rspec_versions' are mandatory
    def aggregate_version (self):
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict()) 
        return {
            'testbed':self.testbed_name(),
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions,
            }  
               
               
    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, \
                                                             users, options):
        """  """
        aggregate = SlabAggregate(self)
        
        slices = SlabSlices(self)
        peer = slices.get_peer(slice_hrn)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record = None 
 
        if not isinstance(creds, list):
            creds = [creds]
    
        if users:
            slice_record = users[0].get('slice_record', {}) 
            logger.debug("SLABDRIVER.PY \t ===============create_sliver \t\
                                        creds %s \r\n \r\n users %s" \
                                        %(creds, users))
            slice_record['user'] = {'keys':users[0]['keys'], \
                                    'email':users[0]['email'], \
                                    'hrn':slice_record['reg-researchers'][0]}
        # parse rspec
        rspec = RSpec(rspec_string)
        logger.debug("SLABDRIVER.PY \t create_sliver \trspec.version \
                                        %s slice_record %s users %s" \
                                        %(rspec.version,slice_record, users))
                                            

        # ensure site record exists?
        # ensure slice record exists
        #Removed options to verify_slice SA 14/08/12
        sfa_slice = slices.verify_slice(slice_hrn, slice_record, peer, \
                                                    sfa_peer)
                                                    
        # ensure person records exists
        #verify_persons returns added persons but since the return value
        #is not used 
        slices.verify_persons(slice_hrn, sfa_slice, users, peer, \
                                                    sfa_peer, options=options)                                           
        #requested_attributes returned by rspec.version.get_slice_attributes() 
        #unused, removed SA 13/08/12
        rspec.version.get_slice_attributes()

        logger.debug("SLABDRIVER.PY create_sliver slice %s " %(sfa_slice))

        # add/remove slice from nodes 
       
        requested_slivers = [node.get('component_id') \
                            for node in rspec.version.get_nodes_with_slivers()\
                            if node.get('authority_id') is self.slab_api.root_auth]
        l = [ node for node in rspec.version.get_nodes_with_slivers() ]
        logger.debug("SLADRIVER \tcreate_sliver requested_slivers \
                                    requested_slivers %s  listnodes %s" \
                                    %(requested_slivers,l))
        #verify_slice_nodes returns nodes, but unused here. Removed SA 13/08/12.
        #slices.verify_slice_nodes(sfa_slice, requested_slivers, peer) 
        
        # add/remove leases
        requested_lease_list = []



        for lease in rspec.version.get_leases():
            single_requested_lease = {}
            logger.debug("SLABDRIVER.PY \tcreate_sliver lease %s " %(lease))
            
            if not lease.get('lease_id'):
                if get_authority(lease['component_id']) == self.slab_api.root_auth:
                    single_requested_lease['hostname'] = \
                                        slab_xrn_to_hostname(\
                                        lease.get('component_id').strip())
                    single_requested_lease['start_time'] = \
                                                        lease.get('start_time')
                    single_requested_lease['duration'] = lease.get('duration')
                    #Check the experiment's duration is valid before adding
                    #the lease to the requested leases list
                    duration_in_seconds = \
                            int(single_requested_lease['duration'])*60
                    if duration_in_seconds > self.slab_api.GetLeaseGranularity():
                        requested_lease_list.append(single_requested_lease)
                     
        #Create dict of leases by start_time, regrouping nodes reserved
        #at the same
        #time, for the same amount of time = one job on OAR
        requested_job_dict = {}
        for lease in requested_lease_list:
            
            #In case it is an asap experiment start_time is empty
            if lease['start_time'] == '':
                lease['start_time'] = '0' 
                
            if lease['start_time'] not in requested_job_dict:
                if isinstance(lease['hostname'], str):
                    lease['hostname'] =  [lease['hostname']]
                    
                requested_job_dict[lease['start_time']] = lease
                
            else :
                job_lease = requested_job_dict[lease['start_time']]
                if lease['duration'] == job_lease['duration'] :
                    job_lease['hostname'].append(lease['hostname'])
                    
          
                
                        
        logger.debug("SLABDRIVER.PY \tcreate_sliver  requested_job_dict %s "\
                                                     %(requested_job_dict))    
        #verify_slice_leases returns the leases , but the return value is unused
        #here. Removed SA 13/08/12           
        slices.verify_slice_leases(sfa_slice, \
                                    requested_job_dict, peer)
        
        return aggregate.get_rspec(slice_xrn=slice_urn, \
                login=sfa_slice['login'], version=rspec.version)
        
        
    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        
        sfa_slice_list  = self.slab_api.GetSlices(slice_filter = slice_hrn, \
                                            slice_filter_type = 'slice_hrn')
        
        if not sfa_slice_list:
            return 1
        
        #Delete all in the slice
        for sfa_slice in sfa_slice_list:

        
            logger.debug("SLABDRIVER.PY delete_sliver slice %s" %(sfa_slice))
            slices = SlabSlices(self)
            # determine if this is a peer slice
        
            peer = slices.get_peer(slice_hrn) 
            #TODO delete_sliver SA : UnBindObjectFromPeer should be 
            #used when there is another 
            #senslab testbed, which is not the case 14/08/12 . 
            
            logger.debug("SLABDRIVER.PY delete_sliver peer %s \r\n \t sfa_slice %s " %(peer, sfa_slice))
            try:
                #if peer:
                    #self.slab_api.UnBindObjectFromPeer('slice', \
                                            #sfa_slice['record_id_slice'], \
                                            #peer, None)
                self.slab_api.DeleteSliceFromNodes(sfa_slice)
                return True
            except :
                return False
            #finally:
                #if peer:
                    #self.slab_api.BindObjectToPeer('slice', \
                                            #sfa_slice['record_id_slice'], \
                                            #peer, sfa_slice['peer_slice_id'])
            #return 1
                
    
    # first 2 args are None in case of resource discovery
    def list_resources (self, slice_urn, slice_hrn, creds, options):
        #cached_requested = options.get('cached', True) 
    
        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = \
                version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_" + \
                                        options.get('info', 'default')
                                        
        # Adding the list_leases option to the caching key
        if options.get('list_leases'):
            version_string = version_string + "_"+options.get('list_leases', 'default')
            
        # Adding geni_available to caching key
        if options.get('geni_available'):
            version_string = version_string + "_" + str(options.get('geni_available'))
    
        # look in cache first
        #if cached_requested and self.cache and not slice_hrn:
            #rspec = self.cache.get(version_string)
            #if rspec:
                #logger.debug("SlabDriver.ListResources: \
                                    #returning cached advertisement")
                #return rspec 
    
        #panos: passing user-defined options
        aggregate = SlabAggregate(self)
        #origin_hrn = Credential(string=creds[0]).get_gid_caller().get_hrn()
        #options.update({'origin_hrn':origin_hrn})
        rspec =  aggregate.get_rspec(slice_xrn=slice_urn, \
                                        version=rspec_version, options=options)
       
        # cache the result
        #if self.cache and not slice_hrn:
            #logger.debug("Slab.ListResources: stores advertisement in cache")
            #self.cache.add(version_string, rspec)
    
        return rspec
        
        
    def list_slices (self, creds, options):
        # look in cache first
        #if self.cache:
            #slices = self.cache.get('slices')
            #if slices:
                #logger.debug("PlDriver.list_slices returns from cache")
                #return slices
    
        # get data from db 

        slices = self.slab_api.GetSlices()        
        logger.debug("SLABDRIVER.PY \tlist_slices hrn %s \r\n \r\n" %(slices))        
        slice_hrns = [slab_slice['hrn'] for slab_slice in slices]

        slice_urns = [hrn_to_urn(slice_hrn, 'slice') \
                                                for slice_hrn in slice_hrns]

        # cache the result
        #if self.cache:
            #logger.debug ("SlabDriver.list_slices stores value in cache")
            #self.cache.add('slices', slice_urns) 
    
        return slice_urns
    
   
    def register (self, sfa_record, hrn, pub_key):
        """ 
        Adding new user, slice, node or site should not be handled
        by SFA.
        
        Adding nodes = OAR
        Adding users = LDAP Senslab
        Adding slice = Import from LDAP users
        Adding site = OAR
        """
        return -1
            
      
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        """No site or node record update allowed in Senslab."""
        
        pointer = old_sfa_record['pointer']
        old_sfa_record_type = old_sfa_record['type']

        # new_key implemented for users only
        if new_key and old_sfa_record_type not in [ 'user' ]:
            raise UnknownSfaType(old_sfa_record_type)
        
        #if (type == "authority"):
            #self.shell.UpdateSite(pointer, new_sfa_record)
    
        if old_sfa_record_type == "slice":
            slab_record = self.slab_api.sfa_fields_to_slab_fields(old_sfa_record_type, \
                                                hrn, new_sfa_record)
            if 'name' in slab_record:
                slab_record.pop('name')
                #Prototype should be UpdateSlice(self,
                #auth, slice_id_or_name, slice_fields)
                #Senslab cannot update slice since slice = job
                #so we must delete and create another job
                self.slab_api.UpdateSlice(pointer, slab_record)
    
        elif old_sfa_record_type == "user":
            update_fields = {}
            all_fields = new_sfa_record
            for key in all_fields.keys():
                if key in ['first_name', 'last_name', 'title', 'email',
                           'password', 'phone', 'url', 'bio', 'accepted_aup',
                           'enabled']:
                    update_fields[key] = all_fields[key]
            self.slab_api.UpdatePerson(pointer, update_fields)
    
            if new_key:
                # must check this key against the previous one if it exists
                persons = self.slab_api.GetPersons(['key_ids'])
                person = persons[0]
                keys = person['key_ids']
                keys = self.slab_api.GetKeys(person['key_ids'])
                
                # Delete all stale keys
                key_exists = False
                for key in keys:
                    if new_key != key['key']:
                        self.slab_api.DeleteKey(key['key_id'])
                    else:
                        key_exists = True
                if not key_exists:
                    self.slab_api.AddPersonKey(pointer, {'key_type': 'ssh', \
                                                    'key': new_key})


        return True
        

    def remove (self, sfa_record):
        sfa_record_type = sfa_record['type']
        hrn = sfa_record['hrn']
        if sfa_record_type == 'user':

            #get user from senslab ldap  
            person = self.slab_api.GetPersons(sfa_record)
            #No registering at a given site in Senslab.
            #Once registered to the LDAP, all senslab sites are
            #accesible.
            if person :
                #Mark account as disabled in ldap
                self.slab_api.DeletePerson(sfa_record)
        elif sfa_record_type == 'slice':
            if self.slab_api.GetSlices(slice_filter = hrn, \
                                    slice_filter_type = 'slice_hrn'):
                self.slab_api.DeleteSlice(sfa_record)

        #elif type == 'authority':
            #if self.GetSites(pointer):
                #self.DeleteSite(pointer)

        return True
            
            
