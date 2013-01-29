#import sys
from httplib import HTTPConnection, HTTPException
import json
#import datetime
#from time import gmtime, strftime 
import os.path
import sys
#import urllib
#import urllib2
from sfa.util.config import Config
#from sfa.util.xrn import hrn_to_urn, get_authority, Xrn, get_leaf

from sfa.util.sfalogging import logger


OAR_REQUEST_POST_URI_DICT = {'POST_job':{'uri': '/oarapi/jobs.json'},
                            'DELETE_jobs_id':{'uri':'/oarapi/jobs/id.json'},
                            }

POST_FORMAT = {'json' : {'content':"application/json", 'object':json},}

#OARpostdatareqfields = {'resource' :"/nodes=", 'command':"sleep", \
                        #'workdir':"/home/", 'walltime':""}

			



class OARrestapi:
    def __init__(self, config_file =  '/etc/sfa/oar_config.py'):
        self.oarserver = {}
       
        
        self.oarserver['uri'] = None
        self.oarserver['postformat'] = 'json'
        
        try:
            execfile(config_file, self.__dict__)
       
            self.config_file = config_file
            # path to configuration data
            self.config_path = os.path.dirname(config_file)
            
        except IOError:
            raise IOError, "Could not find or load the configuration file: %s" \
                            % config_file
        #logger.setLevelDebug()
        self.oarserver['ip'] = self.OAR_IP
        self.oarserver['port'] = self.OAR_PORT
        self.jobstates  = ['Terminated', 'Hold', 'Waiting', 'toLaunch', \
                            'toError', 'toAckReservation', 'Launching', \
                            'Finishing', 'Running', 'Suspended', 'Resuming',\
                            'Error']
                            
        self.parser = OARGETParser(self)
       
            
    def GETRequestToOARRestAPI(self, request, strval=None ,next_page=None, username = None ): 
        self.oarserver['uri'] = \
                            OARGETParser.OARrequests_uri_dict[request]['uri']
        #Get job details with username                   
        if 'owner' in OARGETParser.OARrequests_uri_dict[request] and username:
           self.oarserver['uri'] +=  OARGETParser.OARrequests_uri_dict[request]['owner'] + username
        headers = {}
        data = json.dumps({})
        logger.debug("OARrestapi \tGETRequestToOARRestAPI %s" %(request))
        if strval:
            self.oarserver['uri'] = self.oarserver['uri'].\
                                            replace("id",str(strval))
            
        if next_page:
            self.oarserver['uri'] += next_page
            
        if username:
            headers['X-REMOTE_IDENT'] = username 
            
        print>>sys.stderr, " \r\n \t    OARrestapi \tGETRequestToOARRestAPI %s" %( self.oarserver['uri'])
        logger.debug("OARrestapi: \t  GETRequestToOARRestAPI  \
                        self.oarserver['uri'] %s strval %s" \
                        %(self.oarserver['uri'], strval))
        try :  
            #seems that it does not work if we don't add this
            headers['content-length'] = '0' 

            conn = HTTPConnection(self.oarserver['ip'], \
                                                self.oarserver['port'])
            conn.request("GET", self.oarserver['uri'], data, headers)
            resp = ( conn.getresponse()).read()
            conn.close()
        except HTTPException, error :
            logger.log_exc("GET_OAR_SRVR : Problem with OAR server : %s " \
                                                                    %(error))
            #raise ServerError("GET_OAR_SRVR : Could not reach OARserver")
        try:
            js_dict = json.loads(resp)
            #print "\r\n \t\t\t js_dict keys" , js_dict.keys(), " \r\n", js_dict
            return js_dict
        
        except ValueError, error:
            logger.log_exc("Failed to parse Server Response: %s ERROR %s"\
                                                            %(js_dict, error))
            #raise ServerError("Failed to parse Server Response:" + js)

		
    def POSTRequestToOARRestAPI(self, request, datadict, username=None):
        """ Used to post a job on OAR , along with data associated 
        with the job.
        
        """

        #first check that all params for are OK 
        try:
            self.oarserver['uri'] = OAR_REQUEST_POST_URI_DICT[request]['uri']

        except KeyError:
            logger.log_exc("OARrestapi \tPOSTRequestToOARRestAPI request not \
                             valid")
            return
        if datadict and 'strval' in datadict:
            self.oarserver['uri'] = self.oarserver['uri'].replace("id", \
                                                str(datadict['strval']))
            del datadict['strval']

        data = json.dumps(datadict)
        headers = {'X-REMOTE_IDENT':username, \
                'content-type': POST_FORMAT['json']['content'], \
                'content-length':str(len(data))}     
        try :

            conn = HTTPConnection(self.oarserver['ip'], \
                                        self.oarserver['port'])
            conn.request("POST", self.oarserver['uri'], data, headers)
            resp = (conn.getresponse()).read()
            conn.close()
        except NotConnected:
            logger.log_exc("POSTRequestToOARRestAPI NotConnected ERROR: \
                            data %s \r\n \t\n \t\t headers %s uri %s" \
                            %(data,headers,self.oarserver['uri']))

            #raise ServerError("POST_OAR_SRVR : error")
                
        try:
            answer = json.loads(resp)
            logger.debug("POSTRequestToOARRestAPI : answer %s" %(answer))
            return answer

        except ValueError, error:
            logger.log_exc("Failed to parse Server Response: error %s  \
                            %s" %(error))
            #raise ServerError("Failed to parse Server Response:" + answer)



def AddOarNodeId(tuplelist, value):
    """ Adds Oar internal node id to the nodes attributes """
    
    tuplelist.append(('oar_id', int(value)))

       
def AddNodeNetworkAddr(dictnode, value):
    #Inserts new key. The value associated is a tuple list
    node_id = value
    
    dictnode[node_id] = [('node_id', node_id),('hostname', node_id) ]	
    
    return node_id 
        
def AddNodeSite(tuplelist, value):
    tuplelist.append(('site', str(value)))

def AddNodeRadio(tuplelist, value):
    tuplelist.append(('radio', str(value)))	


def AddMobility(tuplelist, value): 
    if value is 0:
        tuplelist.append(('mobile', 'False'))	
    else :
        tuplelist.append(('mobile', 'True'))

def AddPosX(tuplelist, value):
    tuplelist.append(('posx', value))	

def AddPosY(tuplelist, value):
    tuplelist.append(('posy', value))	
    
def AddPosZ(tuplelist, value):
    tuplelist.append(('posz', value))
    	
def AddBootState(tuplelist, value):
    tuplelist.append(('boot_state', str(value)))
            
#Insert a new node into the dictnode dictionary
def AddNodeId(dictnode, value):
    #Inserts new key. The value associated is a tuple list
    node_id = int(value)
    
    dictnode[node_id] = [('node_id', node_id)]	
    return node_id 

def AddHardwareType(tuplelist, value):
    value_list = value.split(':')
    tuplelist.append(('archi', value_list[0]))	
    tuplelist.append(('radio', value_list[1]))
    
                       
class OARGETParser:
    resources_fulljson_dict = {
        'network_address' : AddNodeNetworkAddr,
        'site': AddNodeSite, 
        'radio': AddNodeRadio,
        'mobile': AddMobility,
        'x': AddPosX,
        'y': AddPosY,
        'z':AddPosZ,
        'archi':AddHardwareType, 
        'state':AddBootState,
        'id' : AddOarNodeId,
        }
        
 
    def __init__(self, srv) :
        self.version_json_dict = { 
            'api_version' : None , 'apilib_version' :None,\
            'api_timezone': None, 'api_timestamp': None, 'oar_version': None ,}
        self.config = Config()
        self.interface_hrn = self.config.SFA_INTERFACE_HRN	
        self.timezone_json_dict = { 
            'timezone': None, 'api_timestamp': None, }
        self.jobs_json_dict = {
            'total' : None, 'links' : [],\
            'offset':None , 'items' : [], }
        self.jobs_table_json_dict = self.jobs_json_dict
        self.jobs_details_json_dict = self.jobs_json_dict		
        self.server = srv
        self.node_dictlist = {}
        self.raw_json = None
        self.site_dict = {}
        self.SendRequest("GET_version")
        
        


    
    def ParseVersion(self) : 
        #print self.raw_json
        #print >>sys.stderr, self.raw_json
        if 'oar_version' in self.raw_json :
            self.version_json_dict.update(api_version = \
                                                self.raw_json['api_version'], 
                            apilib_version = self.raw_json['apilib_version'], 
                            api_timezone = self.raw_json['api_timezone'], 
                            api_timestamp = self.raw_json['api_timestamp'], 
                            oar_version = self.raw_json['oar_version'] )
        else :
            self.version_json_dict.update(api_version = self.raw_json['api'] ,
                            apilib_version = self.raw_json['apilib'],
                            api_timezone = self.raw_json['api_timezone'],
                            api_timestamp = self.raw_json['api_timestamp'],
                            oar_version = self.raw_json['oar'] )
                                
        print self.version_json_dict['apilib_version']
        
            
    def ParseTimezone(self) : 
        api_timestamp = self.raw_json['api_timestamp']
        api_tz = self.raw_json['timezone']
        return api_timestamp, api_tz
            
    def ParseJobs(self) :
        self.jobs_list = []
        print " ParseJobs "
        return self.raw_json
            
    def ParseJobsTable(self) : 
        print "ParseJobsTable"
                
    def ParseJobsDetails (self):
        # currently, this function is not used a lot, 
        #so i have no idea what be usefull to parse, 
        #returning the full json. NT
        #logger.debug("ParseJobsDetails %s " %(self.raw_json))
        return self.raw_json
        

    def ParseJobsIds(self):
        
        job_resources = ['wanted_resources', 'name', 'id', 'start_time', \
                        'state','owner','walltime','message']
        
        
        job_resources_full = ['launching_directory', 'links', \
            'resubmit_job_id', 'owner', 'events', 'message', \
            'scheduled_start', 'id', 'array_id',  'exit_code', \
            'properties', 'state','array_index', 'walltime', \
            'type', 'initial_request', 'stop_time', 'project',\
            'start_time',  'dependencies','api_timestamp','submission_time', \
            'reservation', 'stdout_file', 'types', 'cpuset_name', \
            'name',  'wanted_resources','queue','stderr_file','command']


        job_info = self.raw_json
        #logger.debug("OARESTAPI ParseJobsIds %s" %(self.raw_json))
        values = []
        try:
            for k in job_resources:
                values.append(job_info[k])
            return dict(zip(job_resources, values))
            
        except KeyError:
            logger.log_exc("ParseJobsIds KeyError ")
            

    def ParseJobsIdResources(self):
        """ Parses the json produced by the request 
        /oarapi/jobs/id/resources.json.
        Returns a list of oar node ids that are scheduled for the 
        given job id.
        
        """
        job_resources = []
        for resource in self.raw_json['items']:
            job_resources.append(resource['id'])
            
        #logger.debug("OARESTAPI \tParseJobsIdResources %s" %(self.raw_json))
        return job_resources
            
    def ParseResources(self) :
        """ Parses the json produced by a get_resources request on oar."""
        
        #logger.debug("OARESTAPI \tParseResources " )
        #resources are listed inside the 'items' list from the json
        self.raw_json = self.raw_json['items']
        self.ParseNodes()

    def ParseReservedNodes(self):
        """  Returns an array containing the list of the reserved nodes """
    
        #resources are listed inside the 'items' list from the json
        reservation_list = [] 
        print "ParseReservedNodes_%s" %(self.raw_json['items'])
        job = {}
        #Parse resources info
        for json_element in  self.raw_json['items']:
            #In case it is a real reservation (not asap case)
            if json_element['scheduled_start']:
                job['t_from'] = json_element['scheduled_start']
                job['t_until'] = int(json_element['scheduled_start']) + \
                                                       int(json_element['walltime'])
                #Get resources id list for the job
                job['resource_ids'] = \
                    [ node_dict['id'] for node_dict in json_element['resources'] ]
            else:
                job['t_from'] = "As soon as possible"
                job['t_until'] = "As soon as possible"
                job['resource_ids'] = ["Undefined"]
                
           
            job['state'] = json_element['state'] 
            job['lease_id'] = json_element['id'] 
            
            
            job['user'] = json_element['owner']
            #logger.debug("OARRestapi \tParseReservedNodes job %s" %(job))  
            reservation_list.append(job)
            #reset dict
            job = {}
        return reservation_list
    
    def ParseRunningJobs(self): 
        """ Gets the list of nodes currently in use from the attributes of the
        running jobs.
        
        """
        logger.debug("OARESTAPI \tParseRunningJobs__________________________ ") 
        #resources are listed inside the 'items' list from the json
        nodes = []
        for job in  self.raw_json['items']:
            for node in job['nodes']:
                nodes.append(node['network_address'])
        return nodes
       
        
        
    def ParseDeleteJobs(self):
        """ No need to parse anything in this function.A POST 
        is done to delete the job.
        
        """
        return  
            
    def ParseResourcesFull(self) :
        """ This method is responsible for parsing all the attributes 
        of all the nodes returned by OAR when issuing a get resources full.
        The information from the nodes and the sites are separated.
        Updates the node_dictlist so that the dictionnary of the platform's 
        nodes is available afterwards. 
        
        """
        logger.debug("OARRESTAPI ParseResourcesFull________________________ ")
        #print self.raw_json[1]
        #resources are listed inside the 'items' list from the json
        if self.version_json_dict['apilib_version'] != "0.2.10" :
            self.raw_json = self.raw_json['items']
        self.ParseNodes()
        self.ParseSites()
        return self.node_dictlist
        
    def ParseResourcesFullSites(self) :
        """ UNUSED. Originally used to get information from the sites.
        ParseResourcesFull is used instead.
        
        """
        if self.version_json_dict['apilib_version'] != "0.2.10" :
            self.raw_json = self.raw_json['items']
        self.ParseNodes()
        self.ParseSites()
        return self.site_dict
        

   
    def ParseNodes(self): 
        """ Parse nodes properties from OAR
        Put them into a dictionary with key = node id and value is a dictionary 
        of the node properties and properties'values.
         
        """
        node_id = None
        keys = self.resources_fulljson_dict.keys()
        keys.sort()

        for dictline in self.raw_json:
            node_id = None 
            # dictionary is empty and/or a new node has to be inserted  
            node_id = self.resources_fulljson_dict['network_address'](\
                                self.node_dictlist, dictline['network_address']) 
            for k in keys:
                if k in dictline:
                    if k == 'network_address':
                        continue
                 
                    self.resources_fulljson_dict[k](\
                                    self.node_dictlist[node_id], dictline[k])

            #The last property has been inserted in the property tuple list, 
            #reset node_id 
            #Turn the property tuple list (=dict value) into a dictionary
            self.node_dictlist[node_id] = dict(self.node_dictlist[node_id])
            node_id = None
                    
    def slab_hostname_to_hrn(self, root_auth,  hostname):             
        return root_auth + '.'+ hostname 

                             

    def ParseSites(self):
        """ Returns a list of dictionnaries containing the sites' attributes."""
        
        nodes_per_site = {}
        config = Config()
        #logger.debug(" OARrestapi.py \tParseSites  self.node_dictlist %s"\
                                                        #%(self.node_dictlist))
        # Create a list of nodes per site_id
        for node_id in self.node_dictlist:
            node  = self.node_dictlist[node_id]
            
            if node['site'] not in nodes_per_site:
                nodes_per_site[node['site']] = []
                nodes_per_site[node['site']].append(node['node_id'])
            else:
                if node['node_id'] not in nodes_per_site[node['site']]:
                    nodes_per_site[node['site']].append(node['node_id'])
                        
        #Create a site dictionary whose key is site_login_base (name of the site)
        # and value is a dictionary of properties, including the list 
        #of the node_ids
        for node_id in self.node_dictlist:
            node  = self.node_dictlist[node_id]
            #node.update({'hrn':self.slab_hostname_to_hrn(self.interface_hrn, \
                                            #node['site'],node['hostname'])})
            node.update({'hrn':self.slab_hostname_to_hrn(self.interface_hrn, node['hostname'])})
            self.node_dictlist.update({node_id:node})

            if node['site'] not in self.site_dict:
                self.site_dict[node['site']] = {
                    'site':node['site'],
                    'node_ids':nodes_per_site[node['site']],
                    'latitude':"48.83726",
                    'longitude':"- 2.10336",'name':config.SFA_REGISTRY_ROOT_AUTH,
                    'pcu_ids':[], 'max_slices':None, 'ext_consortium_id':None,
                    'max_slivers':None, 'is_public':True, 'peer_site_id': None,
                    'abbreviated_name':"senslab", 'address_ids': [],
                    'url':"http,//www.senslab.info", 'person_ids':[],
                    'site_tag_ids':[], 'enabled': True,  'slice_ids':[],
                    'date_created': None, 'peer_id': None }     
            #if node['site_login_base'] not in self.site_dict.keys():
                #self.site_dict[node['site_login_base']] = {'login_base':node['site_login_base'],
                                                        #'node_ids':nodes_per_site[node['site_login_base']],
                                                        #'latitude':"48.83726",
                                                        #'longitude':"- 2.10336",'name':"senslab",
                                                        #'pcu_ids':[], 'max_slices':None, 'ext_consortium_id':None,
                                                        #'max_slivers':None, 'is_public':True, 'peer_site_id': None,
                                                        #'abbreviated_name':"senslab", 'address_ids': [],
                                                        #'url':"http,//www.senslab.info", 'person_ids':[],
                                                        #'site_tag_ids':[], 'enabled': True,  'slice_ids':[],
                                                        #'date_created': None, 'peer_id': None } 

                        


    OARrequests_uri_dict = { 
        'GET_version': 
                {'uri':'/oarapi/version.json', 'parse_func': ParseVersion},
        'GET_timezone':
                {'uri':'/oarapi/timezone.json' ,'parse_func': ParseTimezone },
        'GET_jobs': 
                {'uri':'/oarapi/jobs.json','parse_func': ParseJobs},
        'GET_jobs_id': 
                {'uri':'/oarapi/jobs/id.json','parse_func': ParseJobsIds},
        'GET_jobs_id_resources': 
                {'uri':'/oarapi/jobs/id/resources.json',\
                'parse_func': ParseJobsIdResources},
        'GET_jobs_table': 
                {'uri':'/oarapi/jobs/table.json','parse_func': ParseJobsTable},
        'GET_jobs_details': 
                {'uri':'/oarapi/jobs/details.json',\
                'parse_func': ParseJobsDetails},
        'GET_reserved_nodes':
                {'uri':
                '/oarapi/jobs/details.json?state=Running,Waiting,Launching',\
                'owner':'&user=',
                'parse_func':ParseReservedNodes},

                
        'GET_running_jobs':  
                {'uri':'/oarapi/jobs/details.json?state=Running',\
                'parse_func':ParseRunningJobs},
        'GET_resources_full': 
                {'uri':'/oarapi/resources/full.json',\
                'parse_func': ParseResourcesFull},
        'GET_sites':
                {'uri':'/oarapi/resources/full.json',\
                'parse_func': ParseResourcesFullSites},
        'GET_resources':
                {'uri':'/oarapi/resources.json' ,'parse_func': ParseResources},
        'DELETE_jobs_id':
                {'uri':'/oarapi/jobs/id.json' ,'parse_func': ParseDeleteJobs}
        }


    def FindNextPage(self):
        if "links" in self.raw_json:
            for page in self.raw_json['links']:
                if page['rel'] == 'next':
                    self.concatenate = True
                    print>>sys.stderr, " \r\n \t\t FindNextPage  self.concatenate %s" %(self.concatenate )
                    return True, "?"+page['href'].split("?")[1]
        if self.concatenate :
            self.end = True
            print>>sys.stderr, " \r\n \t\t END FindNextPage  self.concatenate %s" %(self.concatenate )
        return False, None
            
    def ConcatenateJsonPages (self, saved_json_list):
        #reset items list

        tmp = {}
        tmp['items'] = []
        print >>sys.stderr, " \r\n ConcatenateJsonPages saved_json_list len ", len(saved_json_list)
        for page in saved_json_list:
            #for node in page['items']:
                #self.raw_json['items'].append(node)
            print>>sys.stderr, " \r\n ConcatenateJsonPages  page['items']len ", len(page['items'])
            tmp['items'].extend(page['items'])
        #print>>sys.stderr, " \r\n ConcatenateJsonPages len ", len(self.raw_json['items'])
        #print>>sys.stderr, " \r\n ConcatenateJsonPages  self.raw_json['items']", self.raw_json['items']        
        return tmp
                        
    def SendRequest(self, request, strval = None , username = None):
        """ Connects to OAR , sends the valid GET requests and uses
        the appropriate json parsing functions.
        
        """
        self.raw_json = None
        next_page = True
        next_offset = None
        save_json = None
        self.concatenate = False
        self.end = False
        a = 0
        save_json = []
        self.raw_json_list = []
        if request in self.OARrequests_uri_dict :
            while next_page:
                self.raw_json = self.server.GETRequestToOARRestAPI(request, \
                                                                strval, \
                                                                next_offset, \
                                                                username)
                
                next_page , next_offset = self.FindNextPage()
                if self.concatenate:
                    #self.raw_json_list.append(self.raw_json)
                    save_json.append(self.raw_json)
            if self.concatenate and self.end :
                #self.raw_json = self.ConcatenateJsonPages(self.raw_json_list) 
                self.raw_json = self.ConcatenateJsonPages(save_json)

            return self.OARrequests_uri_dict[request]['parse_func'](self)
        else:
            logger.error("OARRESTAPI OARGetParse __init__ : ERROR_REQUEST " \
                                                                 %(request))
            
