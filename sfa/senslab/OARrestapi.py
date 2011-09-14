# import modules used here -- sys is a very standard one
import sys
import httplib
import json

oarserver = {}
oarserver['ip'] = '10.127.255.254'
oarserver['port'] = 80

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

#POSTformat = { 'yaml': ("text/yaml", yaml), 
#'json' : ("application/json",json), 
#'http': ("applicaton/x-www-form-urlencoded", html),
#}

POSTformat = {  #'yaml': {'content':"text/yaml", 'object':yaml}
'json' : {'content':"application/json",'object':json}, 
#'http': {'content':"applicaton/x-www-form-urlencoded",'object': html},
}


	
	

#def strip_dictionnary (dict_to_strip):
	#stripped_filter = []
	#stripped_filterdict = {}
	#for f in dict_to_strip :
		#stripped_filter.append(str(f).strip('|'))
		
	#stripped_filterdict = dict(zip(stripped_filter, dict_to_strip.values()))
	
	#return stripped_filterdict
	

#def filter_return_fields( dict_to_filter, return_fields):
	#filtered_dict = {}
	##print>>sys.stderr, " \r\n \t \tfilter_return_fields return fields %s " %(return_fields)
	#for field in return_fields:
		##print>>sys.stderr, " \r\n \t \tfield %s " %(field)	
		#if field in dict_to_filter:
			#filtered_dict[field] = dict_to_filter[field]
	##print>>sys.stderr, " \r\n \t\t filter_return_fields filtered_dict %s " %(filtered_dict)
	#return filtered_dict
	
	
	
#def parse_filter(list_to_filter, param_filter, type_of_list, return_fields=None) :
	#list_type = { 'persons': {'str': 'email','int':'person_id'}, 'keys':{'int':'key_id'}, 'node':{'int':'node_id', 'str':'hostname'}, 'site': {'int':'site_id', 'str':'login_base'}}
	#if type_of_list not in list_type:
		#print>>sys.stderr, " \r\n type_of_list Error  parse_filter %s " %(type_of_list)
		#return []
	
	#print>>sys.stderr, " \r\n ____FIRST ENTRY parse_filter param_filter %s type %s " %(param_filter, type(param_filter))
	#return_filtered_list= []
	
	#for item in list_to_filter:
		#tmp_item = {}
		
		#if type(param_filter) is list :
			
			#for p_filter in param_filter:
				#if type(p_filter) is int:
					#if item[list_type[type_of_list]['int']] == p_filter :
						#if return_fields:
							#tmp_item = filter_return_fields(item,return_fields)
						#else:
							#tmp_item = item
						#return_filtered_list.append(tmp_item)
					
				#if type(p_filter) is str:
					#if item[list_type[type_of_list]['str']] == p_filter :
						#if return_fields:
							#tmp_item = filter_return_fields(item,return_fields)
						#else:
							#tmp_item = item
						#return_filtered_list.append(tmp_item)

					
		#elif type(param_filter) is dict:
			#stripped_filterdict = strip_dictionnary(param_filter)
			
			#tmp_copy = {}
			#tmp_copy = item.copy()
			#key_list = tmp_copy.keys()			
			#for key in key_list:
				#print>>sys.stderr, " \r\n \t\t  key %s " %(key)
				#if key not in stripped_filterdict.keys():
					#del tmp_copy[key] 
					
			
			#print>>sys.stderr, " \r\n tmp_copy %s param_filter %s cmp = %s " %(tmp_copy, param_filter,cmp(tmp_copy, stripped_filterdict))
			
			#if cmp(tmp_copy, stripped_filterdict) == 0:	
				#if return_fields:
					#tmp_item = filter_return_fields(item,return_fields)
				#else:
					
					#tmp_item = item	
				#return_filtered_list.append(tmp_item)
	#return 	return_filtered_list
				
				
class OARrestapi:
	def __init__(self):
		self.oarserver= {}
		self.oarserver['ip'] = '10.127.255.254'
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
			
			
class OARGETParse:
	
			
		
	#Insert a new node into the dictnode dictionary
	def AddNodeId(self,dictnode,value):
		#Inserts new key. The value associated is a tuple list.
		node_id = int(value)
		dictnode[node_id] = [('node_id',node_id) ]	
		return node_id
	
	
	def AddNodeNetworkAddr(self,tuplelist,value):
		#tuplelist.append(('hostname',str(value)))
		tuplelist.append(('hostname',str(value)+'.demolab.fr'))
		tuplelist.append(('site_id',3))	
		
	
	def AddNodeSite(self,tuplelist,value):
		tuplelist.append(('site_login_base',str(value)))	
		
	
	
	def AddNodeRadio(self,tuplelist,value):
		tuplelist.append(('radio',str(value)))	
	
	
	def AddMobility(self,tuplelist,value):
		tuplelist.append(('mobile',int(value)))	
		return 0
	
	
	def AddPosX(self,tuplelist,value):
		tuplelist.append(('posx',value))	
	
	
	def AddPosY(self,tuplelist,value):
		tuplelist.append(('posy',value))	
	
	
	
	def ParseVersion(self) : 
		print "Version" 
		
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
		#resources are listed inside the 'items' list from the json
		self.raw_json = self.raw_json['items']
		self.ParseNodes()
		self.ParseSites()
		
		
	def ParseResourcesFull(self ) :
		#resources are listed inside the 'items' list from the json
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
						node_id = self.resources_fulljson_dict[k](self.node_dictlist, dictline[k])	
					else:
						ret = self.resources_fulljson_dict[k](self.node_dictlist[node_id], dictline[k])
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
			if node['site_id'] not in nodes_per_site.keys():
				nodes_per_site[node['site_id']] = []
				nodes_per_site[node['site_id']].append(node['node_id'])
			else:
				if node['node_id'] not in nodes_per_site[node['site_id']]:
					nodes_per_site[node['site_id']].append(node['node_id'])
		#Create a site dictionary with key is site_login_base (name of the site)
		# and value is a dictionary of properties, including the list of the node_ids
		for node_id in self.node_dictlist.keys():
			node  = self.node_dictlist[node_id]
			if node['site_id'] not in self.site_dict.keys():
				self.site_dict[node['site_login_base']] = [('site_id',node['site_id']),\
									 ('login_base', node['site_login_base']),\
									('node_ids',nodes_per_site[node['site_id']]),\
									('latitude',"48.83726"),\
									('longitude',"- 2.10336")]
				self.site_dict[node['site_login_base']] = dict(self.site_dict[node['site_login_base']])
		print self.site_dict
		
		
	def GetNodesFromOARParse(self):
		print>>sys.stderr, " \r\n =========GetNodesFromOARParse: node_dictlist %s "%(self.node_dictlist)
		return self.node_dictlist

	def GetSitesFromOARParse(self):
		return self.site_dict
	
	def GetJobsFromOARParse(self):
		return self.jobs_list	
	
	def __init__(self, request ):
		self.OARrequests_uri_dict = { 
			'GET_version': {'uri':'/oarapi/version.json', 'parse_func': self.ParseVersion},
			'GET_timezone':{'uri':'/oarapi/timezone.json' ,'parse_func': self.ParseTimezone },
			'GET_jobs': {'uri':'/oarapi/jobs.json','parse_func':self.ParseJobs},
			'GET_jobs_table': {'uri':'/oarapi/jobs/table.json','parse_func':self.ParseJobsTable},
			'GET_jobs_details': {'uri':'/oarapi/jobs/details.json','parse_func': self.ParseJobsDetails},
			'GET_resources_full': {'uri':'/oarapi/resources/full.json','parse_func': self.ParseResourcesFull},
			'GET_resources':{'uri':'/oarapi/resources.json' ,'parse_func':self.ParseResources},
	}
	
		self.resources_fulljson_dict= {
			'resource_id' : self.AddNodeId,
			'network_address' : self.AddNodeNetworkAddr,
			'site': self.AddNodeSite, 
			'radio': self.AddNodeRadio,
			'mobile':self.AddMobility,
			'posx': self.AddPosX,
			'posy': self.AddPosY,
			#'outdoor': ,
			#'scheduler_priority': ,
			#'finaud_decision': ,
			#'deploy': ,
			#'cluster_8': ,
			#'cluster_16' : ,
			#'cluster_32': , 
			#'cluster_64': ,
			#'cluster_128': ,
			#'cluster_256': ,
			#'besteffort': ,
			#'cpu_set' : ,
			#'last_job_date' : ,
			#'desktop_computing' : ,
			#'tray' : ,
			#'links' : ,
			#'expiry_date' : ,
			#'suspended_jobs' : ,
			#'next_finaud_decision' : ,
			#'last_available_upto' : ,
			#'api_timestamp' : , 
			#'state_num' : ,
			#'next_state' : ,
			#'type' : ,
			
			
			
	}
	

		self.version_json_dict= { 'api_version' : None , 'apilib_version' :None,  'api_timezone': None, 'api_timestamp': None, 'oar_version': None ,}
	
		self.timezone_json_dict = { 'timezone': None, 'api_timestamp': None, }
	
		self.jobs_json_dict = { 'total' : None, 'links' : [] , 'offset':None , 'items' : [] , }
		self.jobs_table_json_dict = self.jobs_json_dict
		self.jobs_details_json_dict = self.jobs_json_dict		
		self.server = OARrestapi()
		self.node_dictlist = {}
		self.site_dict = {}
		if request in OARrequests_get_uri_dict:
			self.raw_json = self.server.GETRequestToOARRestAPI(request)
			self.OARrequests_uri_dict[request]['parse_func']()
			
		else:
			print>>sys.stderr, "\r\n OARGetParse __init__ : ERROR_REQUEST "	,request
		

					
	
class OARapi:


	def GetNodes(self,node_filter= None, return_fields=None):
		print>>sys.stderr, " \r\n GetNodes node_filter %s return_fields %s" %(node_filter,return_fields) 
		OARserverapi = OARGETParse( "GET_resources_full")
		node_dict = OARserverapi.GetNodesFromOARParse()
		return_node_list = []
		print>>sys.stderr, " \r\n GetNodes   node_dict %s" %(node_dict) 
		if not (node_filter or return_fields):
			return_node_list = node_dict.values()
			return return_node_list

		return_node_list= parse_filter(node_dict.values(),node_filter ,'node', return_fields)
		return return_node_list

		
	def GetSites(self, site_filter= None, return_fields=None):
		print>>sys.stderr, " \r\n GetSites" 
		OARserverapi = OARGETParse( "GET_resources_full")	
		site_dict = OARserverapi.GetSitesFromOARParse()
		return_site_list = []
		print>>sys.stderr, " \r\n  GetSites sites_dict %s" %(site_dict) 
		if not (site_filter or return_fields):
			return_site_list = site_dict.values()
			return return_site_list
		
		return_site_list = parse_filter(site_dict.values(),site_filter ,'site', return_fields)
		return return_site_list
	
			
	def GetJobs(self):
		print>>sys.stderr, " \r\n GetJobs" 
		OARserverapi = OARGETParse( "GET_jobs")	
		return OARserverapi.GetJobsFromOARParse()
	
	

				
				
#class SenslabImportUsers:


	#def __init__(self):
		#self.person_list = []
		#self.keys_list = []
		#self.InitPersons()
		#self.InitKeys()

	#def InitPersons(self):	
		#persons_per_site = {}
		#person_id = 7
		#persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'a_rioot@senslab.fr', 'key_ids':[1], 'roles': ['pi'], 'role_ids':[20]}
		#person_id = 8
		#persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'lost@senslab.fr','key_ids':[1],'roles': ['pi'], 'role_ids':[20]}
		#for person_id in persons_per_site.keys():
			#person  = persons_per_site[person_id]
			#if person['person_id'] not in self.person_list:
				#self.person_list.append(person)
		#print>>sys.stderr, "InitPersons PERSON DICLIST", self.person_list

	
	#def InitKeys(self):
		#print>>sys.stderr, " InitKeys \r\n"
	
		#self.keys_list = [{'peer_key_id': None, 'key_type': 'ssh', 'key' :
		#"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 7,
		#'key_id':1, 'peer_id':None },{'peer_key_id': None, 'key_type': 'ssh', 'key' :
		#"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 8, 'key_id':1, 'peer_id':None }] 
		
					
	
	#def GetPersons(self, person_filter=None, return_fields=None):
		#print>>sys.stderr, " \r\n GetPersons person_filter %s return_fields %s \t\t person_list%s " %(person_filter,return_fields, self.person_list)
		#if not (person_filter or return_fields):
			#return self.person_list
		#return_person_list= []	
		#return_person_list = parse_filter(self.person_list,person_filter ,'persons', return_fields)
		#return return_person_list
		
	
	#def GetKeys(self,key_filter=None, return_fields=None):
		#return_key_list= []
		#print>>sys.stderr, " \r\n GetKeys" 
	
		#if not (key_filter or return_fields):
			#return self.keys_list
		#return_key_list = parse_filter(self.keys_list,key_filter ,'keys', return_fields)
		#return return_key_list
	
	
			