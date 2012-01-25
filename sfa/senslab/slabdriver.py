import sys

from sfa.util.faults import MissingSfaInfo
from sfa.util.sfalogging import logger
from sfa.storage.table import SfaTable
from sfa.util.defaultdict import defaultdict

from sfa.trust.certificate import *
from sfa.trust.credential import *
from sfa.trust.gid import GID

from sfa.managers.driver import Driver
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.util.xrn import hrn_to_urn
from sfa.util.plxrn import slicename_to_hrn, hostname_to_hrn, hrn_to_pl_slicename, hrn_to_pl_login_base

## thierry: everything that is API-related (i.e. handling incoming requests) 
# is taken care of 
# SlabDriver should be really only about talking to the senslab testbed

## thierry : please avoid wildcard imports :)
from sfa.senslab.OARrestapi import  OARrestapi
from sfa.senslab.LDAPapi import LDAPapi
from sfa.senslab.SenslabImportUsers import SenslabImportUsers
from sfa.senslab.parsing import parse_filter
from sfa.senslab.slabpostgres import SlabDB
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
        self.users = SenslabImportUsers()
        self.time_format = "%Y-%m-%d %H:%M:%S"
        self.db = SlabDB()
        #self.logger=sfa_logger()
        self.cache=None
        

            
    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):
        aggregate = SlabAggregate(self)
        #aggregate = SlabAggregate(self)
        slices = SlabSlices(self)
        peer = slices.get_peer(slice_hrn)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record=None 
        #print>>sys.stderr, " \r\n \r\n   create_sliver  creds %s \r\n \r\n users %s " %(creds,users)
       
        if not isinstance(creds, list):
            creds = [creds]

        #for cred in creds:
            #cred_obj=Credential(string=cred)
            #print >>sys.stderr," \r\n \r\n   create_sliver cred  %s  " %(cred)
            #GIDcall = cred_obj.get_gid_caller()
            #GIDobj = cred_obj.get_gid_object() 
            #print >>sys.stderr," \r\n \r\n   create_sliver GIDobj pubkey %s hrn %s " %(GIDobj.get_pubkey().get_pubkey_string(), GIDobj.get_hrn())
            #print >>sys.stderr," \r\n \r\n   create_sliver GIDcall pubkey %s  hrn %s" %(GIDcall.get_pubkey().get_pubkey_string(),GIDobj.get_hrn())

        
        #tmpcert = GID(string = users[0]['gid'])
        #print >>sys.stderr," \r\n \r\n   create_sliver  tmpcer pubkey %s hrn %s " %(tmpcert.get_pubkey().get_pubkey_string(), tmpcert.get_hrn())
           
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
        
        slices = self.GetSlices({'slice_hrn': slice_hrn})
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
        pl_record = self.sfa_fields_to_pl_fields(type, hrn, sfa_record)
    
        #if type == 'authority':
            #sites = self.shell.GetSites([pl_record['login_base']])
            #if not sites:
                #pointer = self.shell.AddSite(pl_record)
            #else:
                #pointer = sites[0]['site_id']
    
        if type == 'slice':
            acceptable_fields=['url', 'instantiation', 'name', 'description']
            for key in pl_record.keys():
                if key not in acceptable_fields:
                    pl_record.pop(key) 
            print>>sys.stderr, " \r\n \t\t SLABDRIVER.PY register"
            slices = self.GetSlices([pl_record['hrn']])
            if not slices:
                    pointer = self.AddSlice(pl_record)
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
            #login_base = hrn_to_pl_login_base(sfa_record['authority'])
            #nodes = self.GetNodes([pl_record['hostname']])
            #if not nodes:
                #pointer = self.AddNode(login_base, pl_record)
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
            pl_record=self.sfa_fields_to_pl_fields(type, hrn, new_sfa_record)
            if 'name' in pl_record:
                pl_record.pop('name')
                self.UpdateSlice(pointer, pl_record)
    
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
            if self.GetSlices(hrn):
                self.DeleteSlice(hrn)

        #elif type == 'authority':
            #if self.GetSites(pointer):
                #self.DeleteSite(pointer)

        return True
            
    def GetPeers (self,auth = None, peer_filter=None, return_fields=None):
        table = SfaTable()
        return_records = [] 
        records_list =  table.findObjects({'type':'authority+sa'})   
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
            print>>sys.stderr, " \r\n GetPersons person_filter %s return_fields %s return_person_list %s " %(person_filter,return_fields,return_person_list)
            return return_person_list


    def GetJobs(self,job_id= None, resources=True,return_fields=None, details = None):
        #job_resources=['reserved_resources', 'assigned_resources','job_id', 'job_uri', 'assigned_nodes',\
        #'api_timestamp']
        #assigned_res = ['resource_id', 'resource_uri']
        #assigned_n = ['node', 'node_uri']
      
                
	if job_id and resources is False:
            job_info = self.oar.parser.SendRequest("GET_jobs_id", job_id)
            print>>sys.stderr, "\r\n \r\n \t\t GetJobs resources is False job_info %s" %(job_info)

        if job_id and resources :	
            job_info = self.oar.parser.SendRequest("GET_jobs_id_resources", job_id)
            print>>sys.stderr, "\r\n \r\n \t\t GetJobs job_info %s" %(job_info)
            
        if job_info['state'] == 'Terminated':
            print>>sys.stderr, "\r\n \r\n \t\t GetJobs TERMINELEBOUSIN "
            return None
        else:
            return job_info
     
       
     
    def GetNodes(self,node_filter= None, return_fields=None):
		
        node_dict =self.oar.parser.SendRequest("GET_resources_full")

        return_node_list = []
        if not (node_filter or return_fields):
                return_node_list = node_dict.values()
                return return_node_list
    
        return_node_list= parse_filter(node_dict.values(),node_filter ,'node', return_fields)
        return return_node_list
    
    #def GetSites(self, auth, site_filter = None, return_fields=None):
        #self.oar.parser.SendRequest("GET_resources_full")
        #site_dict = self.oar.parser.GetSitesFromOARParse()
        #return_site_list = []
        #site = site_dict.values()[0]
        #if not (site_filter or return_fields):
                #return_site_list = site_dict.values()
                #return return_site_list
        
        #return_site_list = parse_filter(site_dict.values(),site_filter ,'site', return_fields)
        #return return_site_list
    
    def GetSlices(self,slice_filter = None, return_fields=None):
        
        return_slice_list =[]
        sliceslist = self.db.find('slice',columns = ['oar_job_id', 'slice_hrn', 'record_id_slice','record_id_user'], record_filter=slice_filter)
        
        print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  slices %s slice_filter %s " %(sliceslist,slice_filter)
      
       
                    
        if not (slice_filter or return_fields) and sliceslist:
            for sl in sliceslist:
                if sl['oar_job_id'] is not -1: 
                    rslt = self.GetJobs( sl['oar_job_id'],resources=False)
                    print >>sys.stderr, " \r\n \r\n \tSLABRIVER.PY  GetSlices  rslt   %s" %(rslt)
                    
                    if rslt :
                        sl.update(rslt)
                        sl.update({'hrn':str(sl['slice_hrn'])}) 
                        print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  slice SL  %s" %(sl)
                    #If GetJobs is empty, this means the job is now in the 'Terminated' state
                    #Update the slice record
                    else :
                        sl['oar_job_id'] = '-1'
                       
                        sl.update({'hrn':str(sl['slice_hrn'])})
                        print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  TERMINATEDDFDDDDD  %s" %(sl)
                        self.db.update_senslab_slice(sl)
                                 
                                 
            return_slice_list = sliceslist
            print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  return_slice_list  %s" %(return_slice_list)  
            return  return_slice_list
        
        return_slice_list  = parse_filter(sliceslist, slice_filter,'slice', return_fields)
        
        
        for sl in return_slice_list:
                if sl['oar_job_id'] is not -1: 
                    print >>sys.stderr, " \r\n \r\n SLABDRIVER.PY  GetSlices  sl  %s" %(sl)
                    rslt =self.GetJobs( sl['oar_job_id'],resources=False)
                    print >>sys.stderr, " \r\n \r\n SLABRIVER.PY  GetSlices  rslt   %s" %(rslt)
                    if rslt :
                        sl.update(rslt)
                        sl.update({'hrn':str(sl['slice_hrn'])}) 
                        print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  slice SL  %s" %(sl)
                    #If GetJobs is empty, this means the job is now in the 'Terminated' state
                    #Update the slice record
                    else :
                        sl['oar_job_id'] = '-1'
                       
                        sl.update({'hrn':str(sl['slice_hrn'])})
                        print >>sys.stderr, " \r\n \r\n \tSLABDRIVER.PY  GetSlices  TERMINATEDDFDDDDD  %s" %(sl)
                        self.db.update_senslab_slice(sl)
                       
                   
        #print >>sys.stderr, " \r\n \r\n SLABDRIVER.PY  GetSlices  return_slice_list %s" %(return_slice_list)
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
    # @param pl_fields dictionary of PLC fields (output)

    def sfa_fields_to_pl_fields(self, type, hrn, record):

        def convert_ints(tmpdict, int_fields):
            for field in int_fields:
                if field in tmpdict:
                    tmpdict[field] = int(tmpdict[field])

        pl_record = {}
        #for field in record:
        #    pl_record[field] = record[field]
 
        if type == "slice":
            #instantion used in get_slivers ? 
            if not "instantiation" in pl_record:
                pl_record["instantiation"] = "senslab-instantiated"
            pl_record["hrn"] = hrn_to_pl_slicename(hrn)
	    if "url" in record:
               pl_record["url"] = record["url"]
	    if "description" in record:
	        pl_record["description"] = record["description"]
	    if "expires" in record:
	        pl_record["expires"] = int(record["expires"])
                
        #nodes added by OAR only and then imported to SFA
        #elif type == "node":
            #if not "hostname" in pl_record:
                #if not "hostname" in record:
                    #raise MissingSfaInfo("hostname")
                #pl_record["hostname"] = record["hostname"]
            #if not "model" in pl_record:
                #pl_record["model"] = "geni"
                
        #One authority only 
        #elif type == "authority":
            #pl_record["login_base"] = hrn_to_pl_login_base(hrn)

            #if not "name" in pl_record:
                #pl_record["name"] = hrn

            #if not "abbreviated_name" in pl_record:
                #pl_record["abbreviated_name"] = hrn

            #if not "enabled" in pl_record:
                #pl_record["enabled"] = True

            #if not "is_public" in pl_record:
                #pl_record["is_public"] = True

        return pl_record

  
                 
                 
    def AddSliceToNodes(self,  slice_name, added_nodes, slice_user=None):
        print>>sys.stderr, "\r\n \r\n AddSliceToNodes  slice_name %s added_nodes %s username %s" %(slice_name,added_nodes,slice_user )
        site_list = []
        nodeid_list =[]
        resource = ""
        reqdict = {}
        reqdict['property'] ="network_address in ("
        for node in added_nodes:
            #Get the ID of the node : remove the root auth and put the site in a separate list
            tmp = node.strip(self.root_auth+".")
            l = tmp.split("_")
             
            nodeid= (l[len(l)-1]) 
            reqdict['property'] += "'"+ nodeid +"', "
            nodeid_list.append(nodeid)
            site_list.append( l[0] )
            
        reqdict['property'] =  reqdict['property'][0: len( reqdict['property'])-2] +")"
        reqdict['resource'] ="network_address="+ str(len(nodeid_list))
        reqdict['resource']+= ",walltime=" + str(00) + ":" + str(05) + ":" + str(00)
        reqdict['script_path'] = "/bin/sleep 320"
        #reqdict['type'] = "deploy"
        print>>sys.stderr, "\r\n \r\n AddSliceToNodes reqdict   %s \r\n site_list   %s"  %(reqdict,site_list)   
        OAR = OARrestapi()
        answer = OAR.POSTRequestToOARRestAPI('POST_job',reqdict,slice_user)
        print>>sys.stderr, "\r\n \r\n AddSliceToNodes jobid   %s "  %(answer)
        self.db.update('slice',['oar_job_id'], [answer['id']], 'slice_hrn', slice_name)
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
        table = SfaTable()
        person_list, persons = [], {}
        person_list = table.find({'type': 'user', 'pointer': person_ids})
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for  multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        persons = defaultdict(list)
        for person in person_list:
            persons[person['pointer']].append(person)

        # get the pl records
        pl_person_list, pl_persons = [], {}
        pl_person_list = self.GetPersons(person_ids, ['person_id', 'roles'])
        pl_persons = list_to_dict(pl_person_list, 'person_id')
        #print>>sys.stderr, "\r\n \r\n _fill_record_sfa_info ___  _list %s \r\n \t\t SenslabUsers.GetPersons ['person_id', 'roles'] pl_persons %s \r\n records %s" %(pl_person_list, pl_persons,records) 
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
                pl_pis = site_pis[record['site_id']]
                pi_ids = [pi['person_id'] for pi in pl_pis]
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
                    if pointer not in persons or pointer not in pl_persons:
                        # this means there is not sfa or pl record for this user
                        continue   
                    hrns = [person['hrn'] for person in persons[pointer]] 
                    roles = pl_persons[pointer]['roles']   
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
	print >>sys.stderr, "\r\n \t\t BEFORE fill_record_info %s" %(records)	
        if not isinstance(records, list):
            records = [records]
	#print >>sys.stderr, "\r\n \t\t BEFORE fill_record_pl_info %s" %(records)	
        parkour = records 
        try:
            for record in parkour:
                    
                if str(record['type']) == 'slice':
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info record %s" %(record)
                    sfatable = SfaTable()
                    recslice = self.db.find('slice',str(record['hrn']))
                    if isinstance(recslice,list) and len(recslice) == 1:
                        recslice = recslice[0]
                    recuser = sfatable.find(  recslice['record_id_user'], ['hrn'])
                    
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info %s" %(recuser)
                    
                    if isinstance(recuser,list) and len(recuser) == 1:
                        recuser = recuser[0]	          
                    record.update({'PI':[recuser['hrn']],
                    'researcher': [recuser['hrn']],
                    'name':record['hrn'], 
                    'oar_job_id':recslice['oar_job_id'],
                    'node_ids': [],
                    'person_ids':[recslice['record_id_user']]})
                    
                elif str(record['type']) == 'user':  
                    recslice = self.db.find('slice', record_filter={'record_id_user':record['record_id']})
                    for rec in recslice:
                        rec.update({'type':'slice'})
                        rec.update({'hrn':rec['slice_hrn'], 'record_id':rec['record_id_slice']})
                        records.append(rec)
                    print >>sys.stderr, "\r\n \t\t  SLABDRIVER.PY fill_record_info ADDING SLIC EINFO recslice %s" %(recslice) 
                    
        
        except TypeError:
            print >>sys.stderr, "\r\n \t\t SLABDRIVER fill_record_info  EXCEPTION RECORDS : %s" %(records)	
            return
        
        #self.fill_record_pl_info(records)
	##print >>sys.stderr, "\r\n \t\t after fill_record_pl_info %s" %(records)	
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
