#!/usr/bin/python

# import modules used here -- sys is a very standard one
import sys
import httplib
import json
import datetime
import time
from sfa.senslab.parsing import *


				
				
class SenslabImportUsers:


	def __init__(self):
		self.person_list = []
		self.keys_list = []
		self.slices_list= []
		#self.resources_fulldict['keys'] = []
		self.InitPersons()
		self.InitKeys()
		self.InitSlices()
		
		
	def InitSlices(self):
		slices_per_site = {}
		dflt_slice = { 'instantiation': None, 'description': "Senslab Slice Test",  'node_ids': [], 'url': "http://localhost.localdomain/", 'max_nodes': 256, 'site_id': 3,'peer_slice_id': None, 'slice_tag_ids': [], 'peer_id': None, 'hrn' :None}
		for person in self.person_list:
			if 'user' or 'pi' in person['roles']:
				def_slice = {}
				#print>>sys.stderr, "\r\n \rn \t\t _____-----------************def_slice person %s \r\n \rn " %(person['person_id'])
				def_slice['person_ids'] = []
				def_slice['person_ids'].append(person['person_id'])
				def_slice['slice_id'] = person['person_id']
				def_slice['creator_person_id'] = person['person_id']
				extime =  datetime.datetime.utcnow()
				def_slice['created'] = int(time.mktime(extime.timetuple()))
				extime = extime + datetime.timedelta(days=365)
				def_slice['expires'] = int(time.mktime(extime.timetuple()))
				#print>>sys.stderr, "\r\n \rn \t\t _____-----------************def_slice expires  %s \r\n \r\n "%(def_slice['expires'])				
				def_slice['name'] = person['email'].replace('@','_',1)
				#print>>sys.stderr, "\r\n \rn \t\t _____-----------************def_slice %s \r\n \r\n " %(def_slice['name'])
				def_slice.update(dflt_slice)
				self.slices_list.append(def_slice)
	
		print>>sys.stderr, "InitSlices SliceLIST", self.slices_list
		
	def InitPersons(self):	
		persons_per_site = {}
		person_id = 7
		persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'a_rioot@senslab.fr', 'key_ids':[1], 'roles': ['pi'], 'role_ids':[20]}
		person_id = 8
		persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'lost@senslab.fr','key_ids':[1],'roles': ['pi'], 'role_ids':[20]}
		person_id = 9
		persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'user@senslab.fr','key_ids':[1],'roles': ['user'], 'role_ids':[1]}
		for person_id in persons_per_site.keys():
			person  = persons_per_site[person_id]
			if person['person_id'] not in self.person_list:
				self.person_list.append(person)
		print>>sys.stderr, "InitPersons PERSON DICLIST", self.person_list

	
	def InitKeys(self):
		print>>sys.stderr, " InitKeys HEYYYYYYY\r\n"
	
		self.keys_list = [{'peer_key_id': None, 'key_type': 'ssh', 'key' :"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 7, 'key_id':1, 'peer_id':None }, 
		{'peer_key_id': None, 'key_type': 'ssh', 'key' :"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 8, 'key_id':1, 'peer_id':None }, 
		{'peer_key_id': None, 'key_type': 'ssh', 'key' :"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 9, 'key_id':1, 'peer_id':None }] 
		
		
					
	
	def GetPersons(self, person_filter=None, return_fields=None):
		print>>sys.stderr, " \r\n GetPersons person_filter %s return_fields %s  list: %s" %(person_filter,return_fields, self.person_list)
		if not self.person_list :
			print>>sys.stderr, " \r\n ========>GetPersons NO PERSON LIST DAMMIT<========== \r\n" 
			
		if not (person_filter or return_fields):
			return self.person_list
		
		return_person_list= []	
		return_person_list = parse_filter(self.person_list,person_filter ,'persons', return_fields)
		return return_person_list
		
	
	def GetPIs(self,site_id):
		return_person_list= []	
		for person in self.person_list :
			if site_id in person['site_ids'] and 'pi' in person['roles'] :
				return_person_list.append(person['person_id'])
		print>>sys.stderr, " \r\n  GetPIs 	return_person_list %s :" %(return_person_list)	
		return return_person_list
		
				
	def GetKeys(self,key_filter=None, return_fields=None):
		return_key_list= []
		print>>sys.stderr, " \r\n GetKeys" 
	
		if not (key_filter or return_fields):
			return self.keys_list
		return_key_list = parse_filter(self.keys_list,key_filter ,'keys', return_fields)
		return return_key_list
	
	#return_key_list= []
		#print>>sys.stderr, " \r\n GetKeys" 
	
		#if not (key_filter or return_fields):
			#return self.keys_list
		
		#elif key_filter or return_fields:
			#for key in self.keys_list:
				#tmp_key = {}
				#if key_filter:
					#for k_filter in key_filter:
						#if key['key_id'] == k_filter :
							#if return_fields:
								#for field in return_fields:
									#if field in key.keys():
										#tmp_key[field] = key[field]
							#else:
								#tmp_key = key
								
							#print>>sys.stderr, " \r\n tmp_key",tmp_key  
							#return_key_list.append(tmp_key)
				#print>>sys.stderr," \r\n End GetKeys with filter ", return_key_list			
		#return return_key_list
	
	def GetSlices( self,slice_filter=None, return_fields=None):
		return_slice_list= []
		print>>sys.stderr, "\r\n\r\n\t =======================GetSlices " 
		if not (slice_filter or return_fields):
			return self.slices_list
		return_slice_list= parse_filter(self.slices_list, slice_filter,'slice', return_fields)	
		return return_slice_list
	
	
	def AddSlice(self, slice_fields): 
		print>>sys.stderr, " \r\n \r\nAddSlice "
		
		
	def AddPersonToSlice(self,person_id_or_email, slice_id_or_name):
		print>>sys.stderr, " \r\n \r\n  AddPersonToSlice"
		
	def DeletePersonFromSlice(self,person_id_or_email, slice_id_or_name):
		print>>sys.stderr, " \r\n \r\n DeletePersonFromSlice "
