import sys
import httplib
import json
import datetime
from time import gmtime, strftime 

import urllib
import urllib2
from sfa.util.config import Config
from sfa.planetlab.plxrn import PlXrn
from sfa.util.xrn import hrn_to_urn, get_authority,Xrn,get_leaf

from sfa.util.config import Config
from sfa.util.sfalogging import logger

#OARIP='192.168.0.109'
#OARIP='akila.inrialpes.fr'
OARIP='194.199.16.161'
OARrequests_list = ["GET_version", "GET_timezone", "GET_jobs", "GET_jobs_table", "GET_jobs_details",
"GET_resources_full", "GET_resources"]

OARrequests_uri_list = ['/oarapi/version.json','/oarapi/timezone.json', '/oarapi/jobs.json',
'/oarapi/jobs/details.json', '/oarapi/resources/full.json', '/oarapi/resources.json'] 

OARrequests_get_uri_dict = { 'GET_version': '/oarapi/version.json',
			'GET_timezone':'/oarapi/timezone.json' ,
			'GET_jobs': '/oarapi/jobs.json',
                        'GET_jobs_id': '/oarapi/jobs/id.json',
                        'GET_jobs_id_resources': '/oarapi/jobs/id/resources.json',
                        'GET_resources_id': '/oarapi/resources/id.json',
			'GET_jobs_table': '/oarapi/jobs/table.json',
			'GET_jobs_details': '/oarapi/jobs/details.json',
                        'GET_reserved_nodes': '/oarapi/jobs/details.json?state=Runnng,Waiting,Launching',
			'GET_resources_full': '/oarapi/resources/full.json',
			'GET_resources':'/oarapi/resources.json',
                        'GET_sites' : '/oarapi/resources/full.json',
                        
                        
}

OARrequest_post_uri_dict = { 
                            'POST_job':{'uri': '/oarapi/jobs.json'},
                            'DELETE_jobs_id':{'uri':'/oarapi/jobs/id.json'},}

POSTformat = {  #'yaml': {'content':"text/yaml", 'object':yaml}
'json' : {'content':"application/json",'object':json}, 
#'http': {'content':"applicaton/x-www-form-urlencoded",'object': html},
}

OARpostdatareqfields = {'resource' :"/nodes=", 'command':"sleep", 'workdir':"/home/", 'walltime':""}

class OARrestapi:
    def __init__(self):
        self.oarserver= {}
        self.oarserver['ip'] = OARIP
        self.oarserver['port'] = 8800
        self.oarserver['uri'] = None
        self.oarserver['postformat'] = 'json'
        #logger.setLevelDebug()

        self.jobstates  = ['Terminated','Hold','Waiting','toLaunch','toError',\
                            'toAckReservation','Launching','Finishing',\
                            'Running','Suspended','Resuming','Error']
                            
        self.parser = OARGETParser(self)
       
            
    def GETRequestToOARRestAPI(self, request, strval=None , username = None ): 
        self.oarserver['uri'] = OARrequests_get_uri_dict[request] 
        headers = {}
        data = json.dumps({})
        logger.debug("OARrestapi \tGETRequestToOARRestAPI %s" %(request))
        if strval:
          self.oarserver['uri'] = self.oarserver['uri'].replace("id",str(strval))
          logger.debug("OARrestapi: \t  GETRequestToOARRestAPI  self.oarserver['uri'] %s" %( self.oarserver['uri']))
        if username:
            headers['X-REMOTE_IDENT'] = username 
        try :  
            #headers = {'X-REMOTE_IDENT':'avakian',\
            #'content-length':'0'}
            headers['content-length'] = '0' #seems that it does not work if we don't add this
            
            #conn = httplib.HTTPConnection(self.oarserver['ip'],self.oarserver['port'])
            #conn.putheader(headers)
            #conn.endheaders()
            #conn.putrequest("GET",self.oarserver['uri'] ) 
            conn = httplib.HTTPConnection(self.oarserver['ip'],self.oarserver['port'])
            conn.request("GET",self.oarserver['uri'],data , headers )
            resp = ( conn.getresponse()).read()
            #logger.debug("OARrestapi: \t  GETRequestToOARRestAPI  resp %s" %( resp))
            conn.close()
        except:
            raise ServerError("GET_OAR_SRVR : Could not reach OARserver")
        try:
            js = json.loads(resp)
            
            if strval:
                print>>sys.stderr, " \r\n \r\n \t GETRequestToOARRestAPI strval %s js %s" %(strval,js)
            return js
        
        except ValueError:
            raise ServerError("Failed to parse Server Response:" + js)

		
    def POSTRequestToOARRestAPI(self, request, datadict, username=None):
        #first check that all params for are OK 
        
        print>>sys.stderr, " \r\n \r\n POSTRequestToOARRestAPI username",username
        try:
            self.oarserver['uri'] = OARrequest_post_uri_dict[request]['uri']

        except:
            print>>sys.stderr, " \r\n \r\n POSTRequestToOARRestAPI request not in OARrequest_post_uri_dict"
            return
        try:
            if datadict and 'strval' in datadict:
                self.oarserver['uri'] = self.oarserver['uri'].replace("id",str(datadict['strval']))
                del datadict['strval']
        except:
            print>>sys.stderr, " \r\n \r\n POSTRequestToOARRestAPI ERRRRRORRRRRR "
            return
        #if format in POSTformat:
            #if format is 'json':
        data = json.dumps(datadict)
        headers = {'X-REMOTE_IDENT':username,\
                'content-type':POSTformat['json']['content'],\
                'content-length':str(len(data))}     
        try :
            #self.oarserver['postformat'] = POSTformat[format]
            
            conn = httplib.HTTPConnection(self.oarserver['ip'],self.oarserver['port'])
            conn.request("POST",self.oarserver['uri'],data,headers )
            resp = ( conn.getresponse()).read()
            conn.close()
            
            #conn = httplib.HTTPConnection(self.oarserver['ip'],self.oarserver['port'])
            #conn.putrequest("POST",self.oarserver['uri'] )
            #self.oarserver['postformat'] = POSTformat[format]
            #conn.putheader('HTTP X-REMOTE_IDENT', 'avakian')
            #conn.putheader('content-type', self.oarserver['postformat']['content'])
            #conn.putheader('content-length', str(len(data))) 
            #conn.endheaders()
            #conn.send(data)
            #resp = ( conn.getresponse()).read()
            #conn.close()

        except:
            print>>sys.stderr, "\r\n POSTRequestToOARRestAPI  ERROR: data %s \r\n \t\n \t\t headers %s uri %s" %(data,headers,self.oarserver['uri'])
            #raise ServerError("POST_OAR_SRVR : error")
                
        try:
            answer = json.loads(resp)
            print>>sys.stderr, "\r\n POSTRequestToOARRestAPI : ", answer
            return answer

        except ValueError:
            raise ServerError("Failed to parse Server Response:" + answer)


    #def createjobrequest(self, nodelist):
        #datadict = dict(zip(self.OARpostdatareqfields.keys(), self.OARpostdatareqfields.values())
        #for k in datadict:
                #if k is 'resource':
                    #for node in nodelist:
                    #datadict[k] += str(nodelist)

			
class OARGETParser:


    #def AddNodeNetworkAddr(self,tuplelist,value):
        #tuplelist.append(('hostname',str(value)))
        
    def AddNodeNetworkAddr(self,dictnode,value):
        #Inserts new key. The value associated is a tuple list
        node_id = value
        
        dictnode[node_id] = [('node_id',node_id),('hostname',node_id) ]	
        
        return node_id 
            
    def AddNodeSite(self,tuplelist,value):
        tuplelist.append(('site',str(value)))
        	
            
    def AddNodeRadio(self,tuplelist,value):
        tuplelist.append(('radio',str(value)))	
    
    
    def AddMobility(self,tuplelist,value): 
        if value :
            tuplelist.append(('mobile',int(value)))	

    
    
    def AddPosX(self,tuplelist,value):
        tuplelist.append(('posx',value))	
    
    
    def AddPosY(self,tuplelist,value):
        tuplelist.append(('posy',value))	
    
    def AddBootState(self,tuplelist,value):
        tuplelist.append(('boot_state',str(value)))
        	
    #Insert a new node into the dictnode dictionary
    def AddNodeId(self,dictnode,value):
        #Inserts new key. The value associated is a tuple list
        node_id = int(value)
        
        dictnode[node_id] = [('node_id',node_id) ]	
        return node_id
    
    def ParseVersion(self) : 
        #print self.raw_json
        #print >>sys.stderr, self.raw_json
        if 'oar_version' in self.raw_json :
            self.version_json_dict.update(api_version=self.raw_json['api_version'] ,
                            apilib_version=self.raw_json['apilib_version'],
                            api_timezone=self.raw_json['api_timezone'],
                            api_timestamp=self.raw_json['api_timestamp'],
                            oar_version=self.raw_json['oar_version'] )
        else :
            self.version_json_dict.update(api_version=self.raw_json['api'] ,
                            apilib_version=self.raw_json['apilib'],
                            api_timezone=self.raw_json['api_timezone'],
                            api_timestamp=self.raw_json['api_timestamp'],
                            oar_version=self.raw_json['oar'] )
                                
        print self.version_json_dict['apilib_version']
        
            
    def ParseTimezone(self) : 
        api_timestamp=self.raw_json['api_timestamp']
        api_tz=self.raw_json['timezone']
        #readable_time = strftime("%Y-%m-%d %H:%M:%S", gmtime(float(api_timestamp))) 

        return api_timestamp,api_tz
            
    def ParseJobs(self) :
        self.jobs_list = []
        print " ParseJobs "
            
    def ParseJobsTable(self) : 
        print "ParseJobsTable"
                
    def ParseJobsDetails (self):
        # currently, this function is not used a lot, so i have no idea what be usefull to parse, returning the full json. NT
        print >>sys.stderr,"ParseJobsDetails %s " %(self.raw_json)
        return self.raw_json
        

    def ParseJobsIds(self):
        
        job_resources =['assigned_network_address', 'assigned_resources','Job_Id', 'scheduledStart','state','job_user', 'startTime','walltime','message']
        job_resources_full = ['Job_Id', 'scheduledStart', 'resubmit_job_id', 'owner', 'submissionTime', 'message', 'id', 'jobType', 'queue', 'launchingDirectory', 'exit_code', 'state', 'array_index', 'events', 'assigned_network_address', 'cpuset_name', 'initial_request', 'job_user', 'assigned_resources', 'array_id', 'job_id', 'resources_uri', 'dependencies', 'api_timestamp', 'startTime', 'reservation', 'properties', 'types', 'walltime', 'name', 'uri', 'wanted_resources', 'project', 'command']
   
        job_info = self.raw_json
     
        values=[]
        try:
            for k in job_resources:
                values.append(job_info[k])
            return dict(zip(job_resources,values))
            
        except KeyError:
                print>>sys.stderr, " \r\n \t ParseJobsIds Key Error"
            
        
        
        
    def ParseJobsIdResources(self):
        print>>sys.stderr, "ParseJobsIdResources"
            
    def ParseResources(self) :
        print>>sys.stderr, " \r\n  \t\t\t ParseResources__________________________ " 
        #resources are listed inside the 'items' list from the json
        self.raw_json = self.raw_json['items']
        self.ParseNodes()
       
        
    def ParseDeleteJobs(self):
        return  
            
    def ParseResourcesFull(self ) :
        print>>sys.stderr, " \r\n \t\t\t  ParseResourcesFull_____________________________ "
        #print self.raw_json[1]
        #resources are listed inside the 'items' list from the json
        if self.version_json_dict['apilib_version'] != "0.2.10" :
                self.raw_json = self.raw_json['items']
        self.ParseNodes()
        self.ParseSites()
        return self.node_dictlist
        
    def ParseResourcesFullSites(self ) :
        if self.version_json_dict['apilib_version'] != "0.2.10" :
                self.raw_json = self.raw_json['items']
        self.ParseNodes()
        self.ParseSites()
        return self.site_dict
        

    resources_fulljson_dict= {
        'network_address' : AddNodeNetworkAddr,
        'site': AddNodeSite, 
        'radio': AddNodeRadio,
        'mobile': AddMobility,
        'posx': AddPosX,
        'posy': AddPosY,
        'state':AddBootState,
        #'id' : AddNodeId,
        }
      
            
    #Parse nodes properties from OAR
    #Put them into a dictionary with key = node id and value is a dictionary 
    #of the node properties and properties'values.
    def ParseNodes(self):  
        node_id = None
        keys = self.resources_fulljson_dict.keys()
        keys.sort()

        #print >>sys.stderr, " \r\n \r\n \t\t OARrestapi.py ParseNodes self.raw_json %s" %(self.raw_json)
        for dictline in self.raw_json:
            node_id = None 
            # dictionary is empty and/or a new node has to be inserted 
            node_id = self.resources_fulljson_dict['network_address'](self,self.node_dictlist, dictline['network_address'])
            for k in keys:
                if k in dictline:
                    if k == 'network_address':
                        continue
                 
                    
                    self.resources_fulljson_dict[k](self,self.node_dictlist[node_id], dictline[k])
            
            #The last property has been inserted in the property tuple list, reset node_id 
            #Turn the property tuple list (=dict value) into a dictionary
            self.node_dictlist[node_id] = dict(self.node_dictlist[node_id])
            node_id = None
                    
                
    def hostname_to_hrn(self, root_auth, login_base, hostname):
        return PlXrn(auth=root_auth,hostname=login_base + '_' +hostname).get_hrn()
    #Retourne liste de dictionnaires contenant attributs des sites	
    def ParseSites(self):
        nodes_per_site = {}
        config = Config()
        logger.debug(" OARrestapi.py \t ParseSites  self.node_dictlist %s"%(self.node_dictlist))
        # Create a list of nodes per  site_id
        for node_id in self.node_dictlist.keys():
            node  = self.node_dictlist[node_id]
            
            if node['site'] not in nodes_per_site:
                nodes_per_site[node['site']] = []
                nodes_per_site[node['site']].append(node['node_id'])
            else:
                if node['node_id'] not in nodes_per_site[node['site']]:
                    nodes_per_site[node['site']].append(node['node_id'])
                        
        #Create a site dictionary with key is site_login_base (name of the site)
        # and value is a dictionary of properties, including the list of the node_ids
        for node_id in self.node_dictlist.keys():
            node  = self.node_dictlist[node_id]
            node.update({'hrn':self.hostname_to_hrn(self.interface_hrn, node['site'],node['hostname'])})
            #node['hrn'] = self.hostname_to_hrn(self.interface_hrn, node['site_login_base'],node['hostname'])
            self.node_dictlist.update({node_id:node})
            #if node_id is 1:
            if node['site'] not in self.site_dict:
                self.site_dict[node['site']] = {'site':node['site'],
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
        'GET_version': {'uri':'/oarapi/version.json', 'parse_func': ParseVersion},
        'GET_timezone':{'uri':'/oarapi/timezone.json' ,'parse_func': ParseTimezone },
        'GET_jobs': {'uri':'/oarapi/jobs.json','parse_func': ParseJobs},
        'GET_jobs_id': {'uri':'/oarapi/jobs/id.json','parse_func': ParseJobsIds},
        'GET_jobs_id_resources': {'uri':'/oarapi/jobs/id/resources.json','parse_func': ParseJobsIdResources},
        'GET_jobs_table': {'uri':'/oarapi/jobs/table.json','parse_func': ParseJobsTable},
        'GET_jobs_details': {'uri':'/oarapi/jobs/details.json','parse_func': ParseJobsDetails},
        'GET_resources_full': {'uri':'/oarapi/resources/full.json','parse_func': ParseResourcesFull},
        'GET_sites':{'uri':'/oarapi/resources/full.json','parse_func': ParseResourcesFullSites},
        'GET_resources':{'uri':'/oarapi/resources.json' ,'parse_func': ParseResources},
        'DELETE_jobs_id':{'uri':'/oarapi/jobs/id.json' ,'parse_func': ParseDeleteJobs}
        }

    
    def __init__(self, srv ):
        self.version_json_dict= { 'api_version' : None , 'apilib_version' :None,  'api_timezone': None, 'api_timestamp': None, 'oar_version': None ,}
        self.config = Config()
        self.interface_hrn = self.config.SFA_INTERFACE_HRN	
        self.timezone_json_dict = { 'timezone': None, 'api_timestamp': None, }
        self.jobs_json_dict = { 'total' : None, 'links' : [] , 'offset':None , 'items' : [] , }
        self.jobs_table_json_dict = self.jobs_json_dict
        self.jobs_details_json_dict = self.jobs_json_dict		
        self.server = srv
        self.node_dictlist = {}

        self.site_dict = {}
        self.SendRequest("GET_version")

    def SendRequest(self,request, strval = None , username = None):
        if request in OARrequests_get_uri_dict:
            self.raw_json = self.server.GETRequestToOARRestAPI(request,strval,username) 
            return self.OARrequests_uri_dict[request]['parse_func'](self)
        else:
            print>>sys.stderr, "\r\n OARGetParse __init__ : ERROR_REQUEST "	,request
            

  
