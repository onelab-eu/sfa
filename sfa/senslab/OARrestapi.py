# import modules used here -- sys is a very standard one
import sys
import httplib
import json
from sfa.senslab.parsing import *
from sfa.senslab.SenslabImportUsers import *

#OARIP='10.127.255.254'
OARIP='192.168.0.109'


OARrequests_list = ["GET_version", "GET_timezone", "GET_jobs", "GET_jobs_table", "GET_jobs_details",
"GET_resources_full", "GET_resources"]

OARrequests_uri_list = ['/oarapi/version.json','/oarapi/timezone.json', '/oarapi/jobs.json',
'/oarapi/jobs/details.json', '/oarapi/resources/full.json', '/oarapi/resources.json'] 

OARrequests_get_uri_dict = { 'GET_version': '/oarapi/version.json',
			'GET_timezone':'/oarapi/timezone.json' ,
			'GET_jobs': '/oarapi/jobs.json',
			'GET_jobs_table': '/oarapi/jobs/table.json',
			'GET_jobs_details': '/oarapi/jobs/details.json',
			'GET_resources_full': '/oarapi/resources/full.json',
			'GET_resources':'/oarapi/resources.json',
}

POSTformat = {  #'yaml': {'content':"text/yaml", 'object':yaml}
'json' : {'content':"application/json",'object':json}, 
#'http': {'content':"applicaton/x-www-form-urlencoded",'object': html},
}

class OARrestapi:
	def __init__(self):
		self.oarserver= {}
		self.oarserver['ip'] = OARIP
		self.oarserver['port'] = 80
		self.oarserver['uri'] = None
		self.oarserver['postformat'] = None	
		
	def GETRequestToOARRestAPI(self, request ): 
		self.oarserver['uri'] = OARrequests_get_uri_dict[request]
		try :
			conn = httplib.HTTPConnection(self.oarserver['ip'],self.oarserver['port'])
			conn.request("GET",self.oarserver['uri'] )
			resp = ( conn.getresponse()).read()
			conn.close()
		except:
			raise ServerError("GET_OAR_SRVR : Could not reach OARserver")
		try:
			js = json.loads(resp)
			return js
		
		except ValueError:
			raise ServerError("Failed to parse Server Response:" + js)

		
		
	def POSTRequestToOARRestAPI(self, uri,format, data): 
		self.oarserver['uri'] = uri
		if format in POSTformat:
			try :
				conn = httplib.HTTPConnection(self.oarserver['ip'],self.oarserver['port'])
				conn.putrequest("POST",self.oarserver['uri'] )
				self.oarserver['postformat'] = POSTformat[format]
				conn.putheader('content-type', self.oarserver['postformat']['content'])
				conn.putheader('content-length', str(len(data))) 
				conn.endheaders()
				conn.send(data)
				resp = ( conn.getresponse()).read()
				conn.close()
		
			except:
				raise ServerError("POST_OAR_SRVR : error")
				
			try:
				answer = self.oarserver['postformat']['object'].loads(resp)
				return answer
	
			except ValueError:
				raise ServerError("Failed to parse Server Response:" + answer)
		else:
			print>>sys.stderr, "\r\n POSTRequestToOARRestAPI : ERROR_POST_FORMAT"
			
			
class OARGETParser:

	#Insert a new node into the dictnode dictionary
	def AddNodeId(self,dictnode,value):
		#Inserts new key. The value associated is a tuple list.
		node_id = int(value)
		dictnode[node_id] = [('node_id',node_id) ]	
		return node_id
	
	def AddNodeNetworkAddr(self,tuplelist,value):
		tuplelist.append(('hostname',str(value)))
			
		
	def AddNodeSite(self,tuplelist,value):
		tuplelist.append(('site_login_base',str(value)))	
		
	def AddNodeRadio(self,tuplelist,value):
		tuplelist.append(('radio',str(value)))	
	
	
	def AddMobility(self,tuplelist,value):
		if value :
			tuplelist.append(('mobile',int(value)))	
		return 0
	
	
	def AddPosX(self,tuplelist,value):
		tuplelist.append(('posx',value))	
	
	
	def AddPosY(self,tuplelist,value):
		tuplelist.append(('posy',value))	
	
	def AddBootState(self,tuplelist,value):
		tuplelist.append(('boot_state',str(value)))	
	
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
		print " ParseTimezone" 
		
	def ParseJobs(self) :
		self.jobs_list = []
		print " ParseJobs "
		
	def ParseJobsTable(self) : 
		print "ParseJobsTable"
		  
	def ParseJobsDetails (self): 
		print "ParseJobsDetails"
		
	def ParseResources(self) :
		print>>sys.stderr, " \r\n  \t\t\t ParseResources__________________________ " 
		#resources are listed inside the 'items' list from the json
		self.raw_json = self.raw_json['items']
		self.ParseNodes()
		#self.ParseSites()
		
		
		
	def ParseResourcesFull(self ) :
		print>>sys.stderr, " \r\n \t\t\t  ParseResourcesFull_____________________________ "
		#print self.raw_json[1]
		#resources are listed inside the 'items' list from the json
		if self.version_json_dict['apilib_version'] != "0.2.10" :
			self.raw_json = self.raw_json['items']
		self.ParseNodes()
                self.ParseSites()

		
		
	#Parse nodes properties from OAR
	#Put them into a dictionary with key = node id and value is a dictionary 
	#of the node properties and properties'values.
	def ParseNodes(self):  
		node_id = None
		for dictline in self.raw_json:
			for k in dictline.keys():
				if k in self.resources_fulljson_dict:
					# dictionary is empty and/or a new node has to be inserted 
					if node_id is None :
						node_id = self.resources_fulljson_dict[k](self,self.node_dictlist, dictline[k])	
					else:
						ret = self.resources_fulljson_dict[k](self,self.node_dictlist[node_id], dictline[k])
						#If last property has been inserted in the property tuple list, reset node_id 
						if ret == 0:
							#Turn the property tuple list (=dict value) into a dictionary
							self.node_dictlist[node_id] = dict(self.node_dictlist[node_id])
							node_id = None
					
				else:
					pass

	#Retourne liste de dictionnaires contenant attributs des sites	
	def ParseSites(self):
		nodes_per_site = {}
                
		# Create a list of nodes per  site_id
		for node_id in self.node_dictlist.keys():
			node  = self.node_dictlist[node_id]
			if node['site_login_base'] not in nodes_per_site.keys():
				nodes_per_site[node['site_login_base']] = []
				nodes_per_site[node['site_login_base']].append(node['node_id'])
			else:
				if node['node_id'] not in nodes_per_site[node['site_login_base']]:
					nodes_per_site[node['site_login_base']].append(node['node_id'])
		#Create a site dictionary with key is site_login_base (name of the site)
		# and value is a dictionary of properties, including the list of the node_ids
		for node_id in self.node_dictlist.keys():
			node  = self.node_dictlist[node_id]
			if node['site_login_base'] not in self.site_dict.keys():
				self.site_dict[node['site_login_base']] = [('login_base', node['site_login_base']),\
									('node_ids',nodes_per_site[node['site_login_base']]),\
									('latitude',"48.83726"),\
									('longitude',"- 2.10336"),('name',"senslab"),\
									('pcu_ids', []), ('max_slices', None), ('ext_consortium_id', None),\
									('max_slivers', None), ('is_public', True), ('peer_site_id', None),\
									('abbreviated_name', "senslab"), ('address_ids', []),\
									('url', "http,//www.senslab.info"), ('person_ids', []),\
									('site_tag_ids', []), ('enabled', True),  ('slice_ids', []),\
									('date_created', None), ('peer_id', None),]
				self.site_dict[node['site_login_base']] = dict(self.site_dict[node['site_login_base']])
				
		#print>>sys.stderr, "\r\n \r\n =============\t\t ParseSites site dict %s \r\n"%(self.site_dict)
		
		
	def GetNodesFromOARParse(self):
		#print>>sys.stderr, " \r\n =========GetNodesFromOARParse: node_dictlist %s "%(self.node_dictlist)
		return self.node_dictlist

	def GetSitesFromOARParse(self):
		return self.site_dict
	
	def GetJobsFromOARParse(self):
		return self.jobs_list	

	OARrequests_uri_dict = { 
		'GET_version': {'uri':'/oarapi/version.json', 'parse_func': ParseVersion},
		'GET_timezone':{'uri':'/oarapi/timezone.json' ,'parse_func': ParseTimezone },
		'GET_jobs': {'uri':'/oarapi/jobs.json','parse_func': ParseJobs},
		'GET_jobs_table': {'uri':'/oarapi/jobs/table.json','parse_func': ParseJobsTable},
		'GET_jobs_details': {'uri':'/oarapi/jobs/details.json','parse_func': ParseJobsDetails},
		'GET_resources_full': {'uri':'/oarapi/resources/full.json','parse_func': ParseResourcesFull},
		'GET_resources':{'uri':'/oarapi/resources.json' ,'parse_func': ParseResources},
		}
	resources_fulljson_dict= {
		'resource_id' : AddNodeId,
		'network_address' : AddNodeNetworkAddr,
		'site': AddNodeSite, 
		'radio': AddNodeRadio,
		'mobile': AddMobility,
		'posx': AddPosX,
		'posy': AddPosY,
                'state':AddBootState,
		}

	
	def __init__(self, srv ):
		self.version_json_dict= { 'api_version' : None , 'apilib_version' :None,  'api_timezone': None, 'api_timestamp': None, 'oar_version': None ,}
		self.timezone_json_dict = { 'timezone': None, 'api_timestamp': None, }
		self.jobs_json_dict = { 'total' : None, 'links' : [] , 'offset':None , 'items' : [] , }
		self.jobs_table_json_dict = self.jobs_json_dict
		self.jobs_details_json_dict = self.jobs_json_dict		
		self.server = srv
		self.node_dictlist = {}
		self.site_dict = {}
		self.SendRequest("GET_version")

	def SendRequest(self,request):
		if request in OARrequests_get_uri_dict:
			self.raw_json = self.server.GETRequestToOARRestAPI(request)
			self.OARrequests_uri_dict[request]['parse_func'](self)
		else:
			print>>sys.stderr, "\r\n OARGetParse __init__ : ERROR_REQUEST "	,request
		
class OARapi:

	def __init__(self):
		self.server = OARrestapi()
		self.parser = OARGETParser(self.server)

	#GetNodes moved to slabdriver.py
		
	def GetSites(self, site_filter= None, return_fields=None):
		print>>sys.stderr, " \r\n GetSites+++++++++++++++++" 
		self.parser.SendRequest("GET_resources_full")	
		site_dict = self.parser.GetSitesFromOARParse()
		return_site_list = []
		site = site_dict.values()[0]
		Users = SenslabImportUsers()
			
		#print>>sys.stderr, " \r\n  GetSites sites_dict %s site_filter %s  \r\n \r\n  \r\n \r\n------site %s" %(site_dict,site_filter,site ) 
		admins_dict ={'person_ids': Users.GetPIs(site['site_id'])}
		site.update(admins_dict)	
		
		slice_list = Users.GetSlices()
		for sl in slice_list:
			#print>>sys.stderr, " \r\n  GetSites sl %s" %(sl)
			if sl['site_id'] == site['site_id']:
				site['slice_ids'].append(sl['slice_id'])
		
		if not (site_filter or return_fields):
			return_site_list = site_dict.values()
			return return_site_list
		
		return_site_list = parse_filter(site_dict.values(),site_filter ,'site', return_fields)
		return return_site_list
	
			
	def GetJobs(self):
		print>>sys.stderr, " \r\n GetJobs" 
		self.parser.SendRequest("GET_jobs")	
		return self.parser.GetJobsFromOARParse()
	
