import sys
import subprocess

from datetime import datetime
from dateutil import tz 
from time import strftime,gmtime

from sfa.util.faults import MissingSfaInfo , SliverDoesNotExist
from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict

from sfa.storage.record import Record
from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord


from sfa.trust.certificate import *
from sfa.trust.credential import *
from sfa.trust.gid import GID

from sfa.managers.driver import Driver
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.util.xrn import hrn_to_urn, urn_to_sliver_id
from sfa.util.plxrn import slicename_to_hrn, hostname_to_hrn, hrn_to_pl_slicename

## thierry: everything that is API-related (i.e. handling incoming requests) 
# is taken care of 
# SlabDriver should be really only about talking to the senslab testbed

## thierry : please avoid wildcard imports :)
from sfa.senslab.OARrestapi import  OARrestapi
from sfa.senslab.LDAPapi import LDAPapi

from sfa.senslab.parsing import parse_filter
from sfa.senslab.slabpostgres import SlabDB, slab_dbsession,SliceSenslab
from sfa.senslab.slabaggregate import SlabAggregate
from sfa.senslab.slabslices import SlabSlices

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
   # print>>sys.stderr, " \r\n \t\t 1list_to_dict : rec %s  \r\n \t\t list_to_dict key %s" %(recs,key)   
    keys = [rec[key] for rec in recs]
    #print>>sys.stderr, " \r\n \t\t list_to_dict : rec %s  \r\n \t\t list_to_dict keys %s" %(recs,keys)   
    return dict(zip(keys, recs))

# thierry : note
# this inheritance scheme is so that the driver object can receive
# GetNodes or GetSites sorts of calls directly
# and thus minimize the differences in the managers with the pl version
class SlabDriver(Driver):

    def __init__(self, config):
        Driver.__init__ (self, config)
        self.config=config
        self.hrn = config.SFA_INTERFACE_HRN
    
        self.root_auth = config.SFA_REGISTRY_ROOT_AUTH

        
	print >>sys.stderr, "\r\n_____________ SFA SENSLAB DRIVER \r\n" 
        # thierry - just to not break the rest of this code


	#self.oar = OARapi()
        self.oar = OARrestapi()
	self.ldap = LDAPapi()
        #self.users = SenslabImportUsers()
        self.time_format = "%Y-%m-%d %H:%M:%S"
        self.db = SlabDB(config)
        #self.logger=sfa_logger()
        self.cache=None
        

    def sliver_status(self,slice_urn,slice_hrn):
        # receive a status request for slice named urn/hrn urn:publicid:IDN+senslab+nturro_slice hrn senslab.nturro_slice
        # shall return a structure as described in
        # http://groups.geni.net/geni/wiki/GAPI_AM_API_V2#SliverStatus
        # NT : not sure if we should implement this or not, but used by sface.
        

        sl = self.GetSlices(slice_filter= slice_hrn, filter_type = 'slice_hrn')
        if len(sl) is 0:
            raise SliverDoesNotExist("%s  slice_hrn" % (slice_hrn))

        print >>sys.stderr, "\r\n \r\n_____________ Sliver status urn %s hrn %s sl %s \r\n " %(slice_urn,slice_hrn,sl)
        if sl['oar_job_id'] is not -1:
    
            # report about the local nodes only
            nodes_all = self.GetNodes({'hostname':sl['node_ids']},
                            ['node_id', 'hostname','site','boot_state'])
            nodeall_byhostname = dict([(n['hostname'], n) for n in nodes_all])
            nodes = sl['node_ids']
            if len(nodes) is 0:
                raise SliverDoesNotExist("No slivers allocated ") 
                    
             
           
    
            result = {}
            top_level_status = 'unknown'
            if nodes:
                top_level_status = 'ready'
            result['geni_urn'] = slice_urn
            result['pl_login'] = sl['job_user']
            #result['slab_login'] = sl['job_user']
            
            timestamp = float(sl['startTime']) + float(sl['walltime']) 
            result['pl_expires'] = strftime(self.time_format, gmtime(float(timestamp)))
            #result['slab_expires'] = strftime(self.time_format, gmtime(float(timestamp)))
            
            resources = []
            for node in nodes:
                res = {}
                #res['slab_hostname'] = node['hostname']
                #res['slab_boot_state'] = node['boot_state']
                
                res['pl_hostname'] = nodeall_byhostname[node]['hostname']
                res['pl_boot_state'] = nodeall_byhostname[node]['boot_state']
                res['pl_last_contact'] = strftime(self.time_format, gmtime(float(timestamp)))
                sliver_id = urn_to_sliver_id(slice_urn, sl['record_id_slice'],nodeall_byhostname[node]['node_id'] ) 
                res['geni_urn'] = sliver_id 
                if nodeall_byhostname[node]['boot_state'] == 'Alive':
                #if node['boot_state'] == 'Alive':
                    res['geni_status'] = 'ready'
                else:
                    res['geni_status'] = 'failed'
                    top_level_status = 'failed' 
                    
                res['geni_error'] = ''
        
                resources.append(res)
                
            result['geni_status'] = top_level_status
            result['geni_resources'] = resources 
            print >>sys.stderr, "\r\n \r\n_____________ Sliver status resources %s res %s \r\n " %(resources,res)
            return result        
        
        
    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):
        aggregate = SlabAggregate(self)

        slices = SlabSlices(self)
        peer = slices.get_peer(slice_hrn)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record=None 

       
        if not isinstance(creds, list):
            creds = [creds]

           
        if users:
            slice_record = users[0].get('slice_record', {})
    
        # parse rspec
        rspec = RSpec(rspec_string)
        requested_attributes = rspec.version.get_slice_attributes()
        
        # ensure site record exists
        #site = slices.verify_site(slice_hrn, slice_record, peer, sfa_peer, options=options)
        # ensure slice record exists
        slice = slices.verify_slice(slice_hrn, slice_record, peer, sfa_peer, options=options)
        # ensure person records exists
        persons = slices.verify_persons(slice_hrn, slice, users, peer, sfa_peer, options=options)
        # ensure slice attributes exists
        #slices.verify_slice_attributes(slice, requested_attributes, options=options)
        
        # add/remove slice from nodes
        requested_slivers = [node.get('component_name') for node in rspec.version.get_nodes_with_slivers()]
        nodes = slices.verify_slice_nodes(slice, requested_slivers, peer) 
    
      
    
        # handle MyPLC peer association.
        # only used by plc and ple.
        #slices.handle_peer(site, slice, persons, peer)
        
        return aggregate.get_rspec(slice_xrn=slice_urn, version=rspec.version)
        
        
    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        
        slices = self.GetSlices(slice_filter= slice_hrn, filter_type = 'slice_hrn')
        if not slices:
            return 1
        slice = slices[0]
    
        # determine if this is a peer slice
        # xxx I wonder if this would not need to use PlSlices.get_peer instead 
        # in which case plc.peers could be deprecated as this here
        # is the only/last call to this last method in plc.peers
        peer = peers.get_peer(self, slice_hrn)
        try:
            if peer:
                self.UnBindObjectFromPeer('slice', slice['slice_id'], peer)
            self.DeleteSliceFromNodes(slice_hrn, slice['node_ids'])
        finally:
            if peer:
                self.BindObjectToPeer('slice', slice['slice_id'], peer, slice['peer_slice_id'])
        return 1
            
            
            
            
    # first 2 args are None in case of resource discovery
    def list_resources (self, slice_urn, slice_hrn, creds, options):
        #cached_requested = options.get('cached', True) 
    
        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_"+options.get('info', 'default')
    
        # look in cache first
        #if cached_requested and self.cache and not slice_hrn:
            #rspec = self.cache.get(version_string)
            #if rspec:
                #logger.debug("SlabDriver.ListResources: returning cached advertisement")
                #return rspec 
    
        #panos: passing user-defined options
        #print "manager options = ",options
        aggregate = SlabAggregate(self)
        origin_hrn = Credential(string=creds[0]).get_gid_caller().get_hrn()
        print>>sys.stderr, " \r\n \r\n \t SLABDRIVER get_rspec origin_hrn %s" %(origin_hrn)
        options.update({'origin_hrn':origin_hrn})
        print>>sys.stderr, " \r\n \r\n \t SLABDRIVER get_rspec options %s" %(options)
        rspec =  aggregate.get_rspec(slice_xrn=slice_urn, version=rspec_version, 
                                     options=options)
    
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
        print>>sys.stderr, " \r\n \t\t SLABDRIVER.PY list_slices"
        slices = self.GetSlices()
        slice_hrns = [slicename_to_hrn(self.hrn, slice['slice_hrn']) for slice in slices]
        slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]
    
        # cache the result
        #if self.cache:
            #logger.debug ("SlabDriver.list_slices stores value in cache")
            #self.cache.add('slices', slice_urns) 
    
        return slice_urns
    
    #No site or node register supported
    def register (self, sfa_record, hrn, pub_key):
        type = sfa_record['type']
        slab_record = self.sfa_fields_to_slab_fields(type, hrn, sfa_record)
    
        #if type == 'authority':
            #sites = self.shell.GetSites([slab_record['login_base']])
            #if not sites:
                #pointer = self.shell.AddSite(slab_record)
            #else:
                #pointer = sites[0]['site_id']
    
        if type == 'slice':
            acceptable_fields=['url', 'instantiation', 'name', 'description']
            for key in slab_record.keys():
                if key not in acceptable_fields:
                    slab_record.pop(key) 
            print>>sys.stderr, " \r\n \t\t SLABDRIVER.PY register"
            slices = self.GetSlices(slice_filter =slab_record['hrn'], filter_type = 'slice_hrn')
            if not slices:
                    pointer = self.AddSlice(slab_record)
            else:
                    pointer = slices[0]['slice_id']
    
        elif type == 'user':
            persons = self.GetPersons([sfa_record['hrn']])
            if not persons:
                pointer = self.AddPerson(dict(sfa_record))
                #add in LDAP 
            else:
                pointer = persons[0]['person_id']
                
            #Does this make sense to senslab ?
            #if 'enabled' in sfa_record and sfa_record['enabled']:
                #self.UpdatePerson(pointer, {'enabled': sfa_record['enabled']})
                
            # add this person to the site only if she is being added for the first
            # time by sfa and doesont already exist in plc
            if not persons or not persons[0]['site_ids']:
                login_base = get_leaf(sfa_record['authority'])
                self.AddPersonToSite(pointer, login_base)
    
            # What roles should this user have?
            self.AddRoleToPerson('user', pointer)
            # Add the user's key
            if pub_key:
                self.AddPersonKey(pointer, {'key_type' : 'ssh', 'key' : pub_key})
                
        #No node adding outside OAR
        #elif type == 'node':
            #login_base = hrn_to_slab_login_base(sfa_record['authority'])
            #nodes = self.GetNodes([slab_record['hostname']])
            #if not nodes:
                #pointer = self.AddNode(login_base, slab_record)
            #else:
                #pointer = nodes[0]['node_id']
    
        return pointer
            
    #No site or node record update allowed       
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        pointer = old_sfa_record['pointer']
        type = old_sfa_record['type']

        # new_key implemented for users only
        if new_key and type not in [ 'user' ]:
            raise UnknownSfaType(type)
        
        #if (type == "authority"):
            #self.shell.UpdateSite(pointer, new_sfa_record)
    
        if type == "slice":
            slab_record=self.sfa_fields_to_slab_fields(type, hrn, new_sfa_record)
            if 'name' in slab_record:
                slab_record.pop('name')
                self.UpdateSlice(pointer, slab_record)
    
        elif type == "user":
            update_fields = {}
            all_fields = new_sfa_record
            for key in all_fields.keys():
                if key in ['first_name', 'last_name', 'title', 'email',
                           'password', 'phone', 'url', 'bio', 'accepted_aup',
                           'enabled']:
                    update_fields[key] = all_fields[key]
            self.UpdatePerson(pointer, update_fields)
    
            if new_key:
                # must check this key against the previous one if it exists
                persons = self.GetPersons([pointer], ['key_ids'])
                person = persons[0]
                keys = person['key_ids']
                keys = self.GetKeys(person['key_ids'])
                
                # Delete all stale keys
                key_exists = False
                for key in keys:
                    if new_key != key['key']:
                        self.DeleteKey(key['key_id'])
                    else:
                        key_exists = True
                if not key_exists:
                    self.AddPersonKey(pointer, {'key_type': 'ssh', 'key': new_key})
    
        #elif type == "node":
            #self.UpdateNode(pointer, new_sfa_record)

        return True
        

    def remove (self, sfa_record):
        type=sfa_record['type']
        hrn=sfa_record['hrn']
        record_id= sfa_record['record_id']
        if type == 'user':
            username = hrn.split(".")[len(hrn.split(".")) -1]
            #get user in ldap
            persons = self.GetPersons(username)
            # only delete this person if he has site ids. if he doesnt, it probably means
            # he was just removed from a site, not actually deleted
            if persons and persons[0]['site_ids']:
                self.DeletePerson(username)
        elif type == 'slice':
            if self.GetSlices(slice_filter = hrn, filter_type = 'slice_hrn'):
                self.DeleteSlice(hrn)

        #elif type == 'authority':
            #if self.GetSites(pointer):
                #self.DeleteSite(pointer)

        return True
            
    def GetPeers (self,auth = None, peer_filter=None, return_fields=None):

        existing_records = {}
        existing_hrns_by_types= {}
        print >>sys.stderr, "\r\n \r\n SLABDRIVER GetPeers auth = %s, peer_filter %s, return_field %s " %(auth , peer_filter, return_fields)
        all_records = dbsession.query(RegRecord).filter(RegRecord.type.like('%authority%')).all()
        for record in all_records:
            existing_records[record.hrn] = record
            if record.type not in existing_hrns_by_types:
                existing_hrns_by_types[record.type] = [record.hrn]
                print >>sys.stderr, "\r\n \r\n SLABDRIVER GetPeers \t NOT IN existing_hrns_by_types %s " %( existing_hrns_by_types)
            else:
                
                print >>sys.stderr, "\r\n \r\n SLABDRIVER GetPeers \t INNN  type %s hrn %s " %( record.type,record.hrn )
                existing_hrns_by_types.update({record.type:(existing_hrns_by_types[record.type].append(record.hrn))})
                        
        print >>sys.stderr, "\r\n \r\n SLABDRIVER GetPeers        existing_hrns_by_types %s " %( existing_hrns_by_types)
        records_list= [] 
      
        try:
            for hrn in existing_hrns_by_types['authority+sa']:
                records_list.append(existing_records[hrn])
                print >>sys.stderr, "\r\n \r\n SLABDRIVER GetPeers  records_list  %s " %(records_list)
                
        except:
                pass

        if not peer_filter and not return_fields:
            return records_list
        return_records = parse_filter(records_list,peer_filter, 'peers', return_fields) 
 
        return return_records
        
     
            
    def GetPersons(self, person_filter=None, return_fields=None):
        
        person_list = self.ldap.ldapFind({'authority': self.root_auth })
        
        #check = False
        #if person_filter and isinstance(person_filter, dict):
            #for k in  person_filter.keys():
                #if k in person_list[0].keys():
                    #check = True
                    
        return_person_list = parse_filter(person_list,person_filter ,'persons', return_fields)
        if return_person_list:
            print>>sys.stderr, " \r\n GetPersons person_filter %s return_fields %s  " %(person_filter,return_fields)
            return return_person_list

    def GetTimezone(self):
        server_timestamp,server_tz = self.oar.parser.SendRequest("GET_timezone")
        return server_timestamp,server_tz
    

    def DeleteJobs(self, job_id, username):
        if not job_id:
            return
        reqdict = {}
        reqdict['method'] = "delete"
        reqdict['strval'] = str(job_id)
        answer = self.oar.POSTRequestToOARRestAPI('DELETE_jobs_id',reqdict,username)
        print>>sys.stderr, "\r\n \r\n  jobid  DeleteJobs %s "  %(answer)
        
                
    def GetJobs(self,job_id= None, resources=True,return_fields=None, username = None):
        #job_resources=['reserved_resources', 'assigned_resources','job_id', 'job_uri', 'assigned_nodes',\
        #'api_timestamp']
        #assigned_res = ['resource_id', 'resource_uri']
        #assigned_n = ['node', 'node_uri']
     
	if job_id and resources is False:
            req = "GET_jobs_id"
            node_list_k = 'assigned_network_address'
           
        if job_id and resources :
            req = "GET_jobs_id_resources"
            node_list_k = 'reserved_resources' 
               
        #Get job info from OAR    
        job_info = self.oar.parser.SendRequest(req, job_id, username)
        print>>sys.stderr, "\r\n \r\n \t\t GetJobs  %s " %(job_info)
        
        if 'state' in job_info :
            if job_info['state'] == 'Terminated':
                print>>sys.stderr, "\r\n \r\n \t\t GetJobs TERMINELEBOUSIN "
                return None
            if job_info['state'] == 'Error':
                print>>sys.stderr, "\r\n \r\n \t\t GetJobs ERROR message %s " %(job_info)
                return None
        
        #Get a dict of nodes . Key :hostname of the node
        node_list = self.GetNodes() 
        node_hostname_list = []
        for node in node_list:
            node_hostname_list.append(node['hostname'])
        node_dict = dict(zip(node_hostname_list,node_list))
        try :
            liste =job_info[node_list_k] 
            print>>sys.stderr, "\r\n \r\n \t\t GetJobs resources  job_info liste%s" %(liste)
            for k in range(len(liste)):
               job_info[node_list_k][k] = node_dict[job_info[node_list_k][k]]['hostname']
            
            print>>sys.stderr, "\r\n \r\n \t\t YYYYYYYYYYYYGetJobs resources  job_info %s" %(job_info)  
            #Replaces the previous entry "assigned_network_address" / "reserved_resources"
            #with "node_ids"
            job_info.update({'node_ids':job_info[node_list_k]})
            del job_info[node_list_k]
            return job_info
            
        except KeyError:
            print>>sys.stderr, "\r\n \r\n \t\t GetJobs KEYERROR " 
            
    def GetReservedNodes(self):
        # this function returns a list of all the nodes already involved in an oar job

       jobs=self.oar.parser.SendRequest("GET_jobs_details") 
       nodes=[]
       for j in jobs :
          nodes=j['assigned_network_address']+nodes
       return nodes
     
    def GetNodes(self,node_filter= None, return_fields=None):
		
        node_dict =self.oar.parser.SendRequest("GET_resources_full")
        print>>sys.stderr, "\r\n \r\n \t\t  SLABDRIVER.PY GetNodes " 
        return_node_list = []
        if not (node_filter or return_fields):
                return_node_list = node_dict.values()
                return return_node_list
    
        return_node_list= parse_filter(node_dict.values(),node_filter ,'node', return_fields)
        return return_node_list
    
  
    def GetSites(self, site_filter = None, return_fields=None):
        site_dict =self.oar.parser.SendRequest("GET_sites")
        print>>sys.stderr, "\r\n \r\n \t\t  SLABDRIVER.PY GetSites " 
        return_site_list = []
        if not ( site_filter or return_fields):
                return_site_list = site_dict.values()
                return return_site_list
    
        return_site_list = parse_filter(site_dict.values(), site_filter,'site', return_fields)
        return return_site_list
        

    def GetSlices(self,slice_filter = None, filter_type = None, return_fields=None):
        return_slice_list = []
        slicerec  = {}
        rec = {}
        ftypes = ['slice_hrn', 'record_id_user']
        if filter_type and filter_type in ftypes:
            if filter_type == 'slice_hrn':
                slicerec = slab_dbsession.query(SliceSenslab).filter_by(slice_hrn = slice_filter).first()    
            if filter_type == 'record_id_user':
                slicerec = slab_dbsession.query(SliceSenslab).filter_by(record_id_user = slice_filter).first()
                
            if slicerec:
                rec = slicerec.dumpquerytodict()
                login = slicerec.slice_hrn.split(".")[1].split("_")[0]
                print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY slicerec GetSlices   %s " %(slicerec)
                if slicerec.oar_job_id is not -1:
                    rslt = self.GetJobs( slicerec.oar_job_id, resources=False, username = login )
                    print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  GetJobs  %s " %(rslt)     
                    if rslt :
                        rec.update(rslt)
                        rec.update({'hrn':str(rec['slice_hrn'])})
                        #If GetJobs is empty, this means the job is now in the 'Terminated' state
                        #Update the slice record
                    else :
                        self.db.update_job(slice_filter, job_id = -1)
                        rec['oar_job_id'] = -1
                        rec.update({'hrn':str(rec['slice_hrn'])})
            
                print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  rec  %s" %(rec)
                              
            return rec
                
                
        else:
            return_slice_list = slab_dbsession.query(SliceSenslab).all()

        print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  slices %s slice_filter %s " %(return_slice_list,slice_filter)
        
        #if return_fields:
            #return_slice_list  = parse_filter(sliceslist, slice_filter,'slice', return_fields)
        
        
                    
        return return_slice_list
        

        
    
    def testbed_name (self): return "senslab2" 
         
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
          
          
          
          
          
          
    ##
    # Convert SFA fields to PLC fields for use when registering up updating
    # registry record in the PLC database
    #
    # @param type type of record (user, slice, ...)
    # @param hrn human readable name
    # @param sfa_fields dictionary of SFA fields
    # @param slab_fields dictionary of PLC fields (output)

    def sfa_fields_to_slab_fields(self, type, hrn, record):

        def convert_ints(tmpdict, int_fields):
            for field in int_fields:
                if field in tmpdict:
                    tmpdict[field] = int(tmpdict[field])

        slab_record = {}
        #for field in record:
        #    slab_record[field] = record[field]
 
        if type == "slice":
            #instantion used in get_slivers ? 
            if not "instantiation" in slab_record:
                slab_record["instantiation"] = "senslab-instantiated"
            slab_record["hrn"] = hrn_to_pl_slicename(hrn)
            print >>sys.stderr, "\r\n \r\n \t SLABDRIVER.PY sfa_fields_to_slab_fields slab_record %s hrn_to_pl_slicename(hrn) hrn %s " %(slab_record['hrn'], hrn)
	    if "url" in record:
               slab_record["url"] = record["url"]
	    if "description" in record:
	        slab_record["description"] = record["description"]
	    if "expires" in record:
	        slab_record["expires"] = int(record["expires"])
                
        #nodes added by OAR only and then imported to SFA
        #elif type == "node":
            #if not "hostname" in slab_record:
                #if not "hostname" in record:
                    #raise MissingSfaInfo("hostname")
                #slab_record["hostname"] = record["hostname"]
            #if not "model" in slab_record:
                #slab_record["model"] = "geni"
                
        #One authority only 
        #elif type == "authority":
            #slab_record["login_base"] = hrn_to_slab_login_base(hrn)

            #if not "name" in slab_record:
                #slab_record["name"] = hrn

            #if not "abbreviated_name" in slab_record:
                #slab_record["abbreviated_name"] = hrn

            #if not "enabled" in slab_record:
                #slab_record["enabled"] = True

            #if not "is_public" in slab_record:
                #slab_record["is_public"] = True

        return slab_record

  
                 
                 
    def AddSliceToNodes(self,  slice_name, added_nodes, slice_user=None):
       
        site_list = []
        nodeid_list =[]
        resource = ""
        reqdict = {}
        reqdict['property'] ="network_address in ("
        for node in added_nodes:
            #Get the ID of the node : remove the root auth and put the site in a separate list
            s=node.split(".")
            # NT: it's not clear for me if the nodenames will have the senslab prefix
            # so lets take the last part only, for now.
            lastpart=s[-1]
            #if s[0] == self.root_auth :
            # Again here it's not clear if nodes will be prefixed with <site>_, lets split and tanke the last part for now.
            s=lastpart.split("_")
            nodeid=s[-1]
            reqdict['property'] += "'"+ nodeid +"', "
            nodeid_list.append(nodeid)
            #site_list.append( l[0] )
        reqdict['property'] =  reqdict['property'][0: len( reqdict['property'])-2] +")"
        reqdict['resource'] ="network_address="+ str(len(nodeid_list))
        reqdict['resource']+= ",walltime=" + str(00) + ":" + str(12) + ":" + str(20) #+2 min 20
        reqdict['script_path'] = "/bin/sleep 620" #+20 sec
        reqdict['type'] = "deploy" 
        reqdict['directory']= ""
        reqdict['name']= "TestSandrine"
        # reservations are performed in the oar server timebase, so :
        # 1- we get the server time(in UTC tz )/server timezone
        # 2- convert the server UTC time in its timezone
        # 3- add a custom delay to this time
        # 4- convert this time to a readable form and it for the reservation request.
        server_timestamp,server_tz = self.GetTimezone()
        s_tz=tz.gettz(server_tz)
        UTC_zone = tz.gettz("UTC")
        #weird... datetime.fromtimestamp should work since we do from datetime import datetime
        utc_server= datetime.datetime.fromtimestamp(float(server_timestamp)+20,UTC_zone)
        server_localtime=utc_server.astimezone(s_tz)

        print>>sys.stderr, "\r\n \r\n AddSliceToNodes  slice_name %s added_nodes %s username %s reqdict %s " %(slice_name,added_nodes,slice_user, reqdict)
        readable_time = server_localtime.strftime(self.time_format)

        print >>sys.stderr,"  \r\n \r\n \t\t\t\tAPRES ParseTimezone readable_time %s timestanp %s  " %(readable_time ,server_timestamp)
        reqdict['reservation'] = readable_time
         
        # first step : start the OAR job
        print>>sys.stderr, "\r\n \r\n AddSliceToNodes reqdict   %s \r\n site_list   %s"  %(reqdict,site_list)   
        #OAR = OARrestapi()
        answer = self.oar.POSTRequestToOARRestAPI('POST_job',reqdict,slice_user)
        print>>sys.stderr, "\r\n \r\n AddSliceToNodes jobid   %s "  %(answer)
        #self.db.update('slice',['oar_job_id'], [answer['id']], 'slice_hrn', slice_name)
               

        self.db.update_job( slice_name, job_id = answer['id'] )
        jobid=answer['id']
        print>>sys.stderr, "\r\n \r\n AddSliceToNodes jobid    %s added_nodes  %s slice_user %s"  %(jobid,added_nodes,slice_user)  
        # second step : configure the experiment
        # we need to store the nodes in a yaml (well...) file like this :
        # [1,56,23,14,45,75] with name /tmp/sfa<jobid>.json
        f=open('/tmp/sfa/'+str(jobid)+'.json','w')
        f.write('[')
        f.write(str(added_nodes[0].strip('node')))
        for node in added_nodes[1:len(added_nodes)] :
            f.write(','+node.strip('node'))
        f.write(']')
        f.close()
        
        # third step : call the senslab-experiment wrapper
        #command= "java -jar target/sfa-1.0-jar-with-dependencies.jar "+str(jobid)+" "+slice_user
        javacmdline="/usr/bin/java"
        jarname="/opt/senslabexperimentwrapper/sfa-1.0-jar-with-dependencies.jar"
        #ret=subprocess.check_output(["/usr/bin/java", "-jar", ", str(jobid), slice_user])
        output = subprocess.Popen([javacmdline, "-jar", jarname, str(jobid), slice_user],stdout=subprocess.PIPE).communicate()[0]

        print>>sys.stderr, "\r\n \r\n AddSliceToNodes wrapper returns   %s "  %(output)
        return 
    

        
        
    def DeleteSliceFromNodes(self, slice_name, deleted_nodes):
        return   
    
 

    def fill_record_sfa_info(self, records):

        def startswith(prefix, values):
            return [value for value in values if value.startswith(prefix)]

        # get person ids
        person_ids = []
        site_ids = []
        for record in records:
            person_ids.extend(record.get("person_ids", []))
            site_ids.extend(record.get("site_ids", [])) 
            if 'site_id' in record:
                site_ids.append(record['site_id']) 
        	
	#print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___person_ids %s \r\n \t\t site_ids %s " %(person_ids, site_ids)
	
        # get all pis from the sites we've encountered
        # and store them in a dictionary keyed on site_id 
        site_pis = {}
        if site_ids:
            pi_filter = {'|roles': ['pi'], '|site_ids': site_ids} 
            pi_list = self.GetPersons( pi_filter, ['person_id', 'site_ids'])
	    #print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___ GetPersons ['person_id', 'site_ids'] pi_ilist %s" %(pi_list)

            for pi in pi_list:
                # we will need the pi's hrns also
                person_ids.append(pi['person_id'])
                
                # we also need to keep track of the sites these pis
                # belong to
                for site_id in pi['site_ids']:
                    if site_id in site_pis:
                        site_pis[site_id].append(pi)
                    else:
                        site_pis[site_id] = [pi]
                 
        # get sfa records for all records associated with these records.   
        # we'll replace pl ids (person_ids) with hrns from the sfa records
        # we obtain
        
        # get the sfa records
        #table = SfaTable()
        existing_records = {}
        all_records = dbsession.query(RegRecord).all()
        for record in all_records:
            existing_records[(record.type,record.pointer)] = record
            
        print >>sys.stderr, " \r\r\n SLABDRIVER fill_record_sfa_info existing_records %s "  %(existing_records)
        person_list, persons = [], {}
        #person_list = table.find({'type': 'user', 'pointer': person_ids})
        try:
            for p_id in person_ids:
                person_list.append( existing_records.get(('user',p_id)))
        except KeyError:
            print >>sys.stderr, " \r\r\n SLABDRIVER fill_record_sfa_info ERRRRRRRRRROR"
                 
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for  multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        persons = defaultdict(list)
        for person in person_list:
            persons[person['pointer']].append(person)

        # get the pl records
        slab_person_list, slab_persons = [], {}
        slab_person_list = self.GetPersons(person_ids, ['person_id', 'roles'])
        slab_persons = list_to_dict(slab_person_list, 'person_id')
        #print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___  _list %s \r\n \t\t SenslabUsers.GetPersons ['person_id', 'roles'] slab_persons %s \r\n records %s" %(slab_person_list, slab_persons,records) 
        # fill sfa info
	
        for record in records:
            # skip records with no pl info (top level authorities)
	    #Sandrine 24 oct 11 2 lines
            #if record['pointer'] == -1:
                #continue 
            sfa_info = {}
            type = record['type']
            if (type == "slice"):
                # all slice users are researchers
		#record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')  ? besoin ou pas ?
                record['PI'] = []
                record['researcher'] = []
		for person_id in record.get('person_ids', []):
			 #Sandrine 24 oct 11 line
                #for person_id in record['person_ids']:
                    hrns = [person['hrn'] for person in persons[person_id]]
                    record['researcher'].extend(hrns)                

                # pis at the slice's site
                slab_pis = site_pis[record['site_id']]
                pi_ids = [pi['person_id'] for pi in slab_pis]
                for person_id in pi_ids:
                    hrns = [person['hrn'] for person in persons[person_id]]
                    record['PI'].extend(hrns)
                record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')
                record['geni_creator'] = record['PI'] 
                
            elif (type == "authority"):
                record['PI'] = []
                record['operator'] = []
                record['owner'] = []
                for pointer in record['person_ids']:
                    if pointer not in persons or pointer not in slab_persons:
                        # this means there is not sfa or pl record for this user
                        continue   
                    hrns = [person['hrn'] for person in persons[pointer]] 
                    roles = slab_persons[pointer]['roles']   
                    if 'pi' in roles:
                        record['PI'].extend(hrns)
                    if 'tech' in roles:
                        record['operator'].extend(hrns)
                    if 'admin' in roles:
                        record['owner'].extend(hrns)
                    # xxx TODO: OrganizationName
            elif (type == "node"):
                sfa_info['dns'] = record.get("hostname", "")
                # xxx TODO: URI, LatLong, IP, DNS
    
            elif (type == "user"):
                 sfa_info['email'] = record.get("email", "")
                 sfa_info['geni_urn'] = hrn_to_urn(record['hrn'], 'user')
                 sfa_info['geni_certificate'] = record['gid'] 
                # xxx TODO: PostalAddress, Phone
		
            #print>>sys.stderr, "\r\n \r\rn \t\t \t <<<<<<<<<<<<<<<<<<<<<<<<  fill_record_sfa_info sfa_info %s  \r\n record %s : "%(sfa_info,record)  
            record.update(sfa_info)
            
    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)
    
    def fill_record_info(self, records):
        """
        Given a SFA record, fill in the senslab specific and SFA specific
        fields in the record. 
        """
                    
        print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info 000000000 fill_record_info %s  " %(records)
        if not isinstance(records, list):
            records = [records]

        parkour = records 
        try:
            for record in parkour:
                    
                if str(record['type']) == 'slice':
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY  fill_record_info \t \t record %s" %(record)
                    #sfatable = SfaTable()
                    
                    #existing_records_by_id = {}
                    #all_records = dbsession.query(RegRecord).all()
                    #for rec in all_records:
                        #existing_records_by_id[rec.record_id] = rec
                    #print >>sys.stderr, "\r\n \t\t SLABDRIVER.PY  fill_record_info \t\t existing_records_by_id %s" %(existing_records_by_id[record['record_id']])
                        
                    #recslice = self.db.find('slice',{'slice_hrn':str(record['hrn'])}) 
                    #recslice = slab_dbsession.query(SliceSenslab).filter_by(slice_hrn = str(record['hrn'])).first()
                    recslice = self.GetSlices(slice_filter =  str(record['hrn']), filter_type = 'slice_hrn')
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info \t\t HOY HOY reclise %s" %(recslice)
                    #if isinstance(recslice,list) and len(recslice) == 1:
                        #recslice = recslice[0]
                   
                    recuser = dbsession.query(RegRecord).filter_by(record_id = recslice['record_id_user']).first()
                    #existing_records_by_id[recslice['record_id_user']]
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info \t\t recuser %s" %(recuser)
                    
          
                    record.update({'PI':[recuser.hrn],
                    'researcher': [recuser.hrn],
                    'name':record['hrn'], 
                    'oar_job_id':recslice['oar_job_id'],
                    'node_ids': [],
                    'person_ids':[recslice['record_id_user']]})
                    
                elif str(record['type']) == 'user':
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info USEEEEEEEEEERDESU!" 

                    rec = self.GetSlices(slice_filter = record['record_id'], filter_type = 'record_id_user')
                    #Append record in records list, therfore fetches user and slice info again(one more loop)
                    #Will update PIs and researcher for the slice

                    rec.update({'type':'slice','hrn':rec['slice_hrn']})
                    records.append(rec)
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info ADDING SLIC EINFO rec %s" %(rec) 
                    
            print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info OKrecords %s" %(records) 
        except TypeError:
            print >>sys.stderr, "\r\n \t\t SLABDRIVER fill_record_info  EXCEPTION RECORDS : %s" %(records)	
            return
        
        #self.fill_record_slab_info(records)
	##print >>sys.stderr, "\r\n \t\t after fill_record_slab_info %s" %(records)	
        #self.fill_record_sfa_info(records)
	#print >>sys.stderr, "\r\n \t\t after fill_record_sfa_info"
	
        

    
        
    #def update_membership_list(self, oldRecord, record, listName, addFunc, delFunc):
        ## get a list of the HRNs tht are members of the old and new records
        #if oldRecord:
            #oldList = oldRecord.get(listName, [])
        #else:
            #oldList = []     
        #newList = record.get(listName, [])

        ## if the lists are the same, then we don't have to update anything
        #if (oldList == newList):
            #return

        ## build a list of the new person ids, by looking up each person to get
        ## their pointer
        #newIdList = []
        #table = SfaTable()
        #records = table.find({'type': 'user', 'hrn': newList})
        #for rec in records:
            #newIdList.append(rec['pointer'])

        ## build a list of the old person ids from the person_ids field 
        #if oldRecord:
            #oldIdList = oldRecord.get("person_ids", [])
            #containerId = oldRecord.get_pointer()
        #else:
            ## if oldRecord==None, then we are doing a Register, instead of an
            ## update.
            #oldIdList = []
            #containerId = record.get_pointer()

    ## add people who are in the new list, but not the oldList
        #for personId in newIdList:
            #if not (personId in oldIdList):
                #addFunc(self.plauth, personId, containerId)

        ## remove people who are in the old list, but not the new list
        #for personId in oldIdList:
            #if not (personId in newIdList):
                #delFunc(self.plauth, personId, containerId)

    #def update_membership(self, oldRecord, record):
        #print >>sys.stderr, " \r\n \r\n ***SLABDRIVER.PY update_membership record ", record
        #if record.type == "slice":
            #self.update_membership_list(oldRecord, record, 'researcher',
                                        #self.users.AddPersonToSlice,
                                        #self.users.DeletePersonFromSlice)
        #elif record.type == "authority":
            ## xxx TODO
            #pass

### thierry
# I don't think you plan on running a component manager at this point
# let me clean up the mess of ComponentAPI that is deprecated anyways
