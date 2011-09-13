#!/usr/bin/python

# import modules used here -- sys is a very standard one
import sys
import httplib
import json




def strip_dictionnary (dict_to_strip):
	stripped_filter = []
	stripped_filterdict = {}
	for f in dict_to_strip :
		stripped_filter.append(str(f).strip('|'))
		
	stripped_filterdict = dict(zip(stripped_filter, dict_to_strip.values()))
	
	return stripped_filterdict
	

def filter_return_fields( dict_to_filter, return_fields):
	filtered_dict = {}
	#print>>sys.stderr, " \r\n \t \tfilter_return_fields return fields %s " %(return_fields)
	for field in return_fields:
		#print>>sys.stderr, " \r\n \t \tfield %s " %(field)	
		if field in dict_to_filter:
			filtered_dict[field] = dict_to_filter[field]
	#print>>sys.stderr, " \r\n \t\t filter_return_fields filtered_dict %s " %(filtered_dict)
	return filtered_dict
	
	
	
def parse_filter(list_to_filter, param_filter, type_of_list, return_fields=None) :
	list_type = { 'persons': {'str': 'email','int':'person_id'}, 'keys':{'int':'key_id'}}
	if type_of_list not in list_type:
		print>>sys.stderr, " \r\n type_of_list Error  parse_filter %s " %(type_of_list)
		return []
	
	print>>sys.stderr, " \r\n ____FIRST ENTRY parse_filter param_filter %s type %s " %(param_filter, type(param_filter))
	return_filtered_list= []
	
	for item in list_to_filter:
		tmp_item = {}
		
		if type(param_filter) is list :
			#print>>sys.stderr, " \r\n p_filter LIST %s " %(param_filter)
			
			for p_filter in param_filter:
				#print>>sys.stderr, " \r\n p_filter %s \t item %s " %(p_filter,item)
				if type(p_filter) is int:
					if item[list_type[type_of_list]['int']] == p_filter :
						if return_fields:
							tmp_item = filter_return_fields(item,return_fields)
						else:
							tmp_item = item
						return_filtered_list.append(tmp_item)
					#print>>sys.stderr, " \r\n 1tmp_item",tmp_item	
					
				if type(p_filter) is str:
					if item[list_type[type_of_list]['str']] == p_filter :
						if return_fields:
							tmp_item = filter_return_fields(item,return_fields)
						else:
							tmp_item = item
						return_filtered_list.append(tmp_item)
					#print>>sys.stderr, " \r\n 2tmp_item",tmp_item
					
		elif type(param_filter) is dict:
			stripped_filterdict = strip_dictionnary(param_filter)
			
			tmp_copy = {}
			tmp_copy = item.copy()
			#print>>sys.stderr, " \r\n \t\t ________tmp_copy %s " %(tmp_copy)
			key_list = tmp_copy.keys()			
			for key in key_list:
				print>>sys.stderr, " \r\n \t\t  key %s " %(key)
				if key not in stripped_filterdict.keys():
					del tmp_copy[key] 
					
			
			print>>sys.stderr, " \r\n tmp_copy %s param_filter %s cmp = %s " %(tmp_copy, param_filter,cmp(tmp_copy, stripped_filterdict))
			
			if cmp(tmp_copy, stripped_filterdict) == 0:	
				if return_fields:
					tmp_item = filter_return_fields(item,return_fields)
				else:
					
					tmp_item = item	
				return_filtered_list.append(tmp_item)
		
		return 	return_filtered_list
				
				
class SenslabImportUsers:


	def __init__(self):
		self.person_list = []
		self.keys_list = []
		#self.resources_fulldict['keys'] = []
		self.InitPersons()
		self.InitKeys()

	def InitPersons(self):	
		persons_per_site = {}
		person_id = 7
		persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'a_rioot@senslab.fr', 'key_ids':[1], 'roles': ['pi'], 'role_ids':[20]}
		person_id = 8
		persons_per_site[person_id] = {'person_id': person_id,'site_ids': [3],'email': 'lost@senslab.fr','key_ids':[1],'roles': ['pi'], 'role_ids':[20]}
		for person_id in persons_per_site.keys():
			person  = persons_per_site[person_id]
			if person['person_id'] not in self.person_list:
				self.person_list.append(person)
		print>>sys.stderr, "InitPersons PERSON DICLIST", self.person_list

	
	def InitKeys(self):
		print>>sys.stderr, " InitKeys HEYYYYYYY\r\n"
	
		self.keys_list = [{'peer_key_id': None, 'key_type': 'ssh', 'key' :"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 7, 'key_id':1, 'peer_id':None }, {'peer_key_id': None, 'key_type': 'ssh', 'key' :"ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEArcdW0X2la754SoFE+URbDsYP07AZJjrspMlvUc6u+4o6JpGRkqiv7XdkgOMIn6w3DF3cYCcA1Mc6XSG7gSD7eQx614cjlLmXzHpxSeidSs/LgZaAQpq9aQ0KhEiFxg0gp8TPeB5Z37YOPUumvcJr1ArwL/8tAOx3ClwgRhccr2HOe10YtZbMEboCarTlzNHiGolo7RYIJjGuG2RBSeAg6SMZrtnn0OdKBwp3iUlOfkS98eirVtWUp+G5+SZggip3fS3k5Oj7OPr1qauva8Rizt02Shz30DN9ikFNqV2KuPg54nC27/DQsQ6gtycARRVY91VvchmOk0HxFiW/9kS2GQ== root@FlabFedora2",'person_id': 8, 'key_id':1, 'peer_id':None }] 
		
		
					
	
	def GetPersons(self, person_filter=None, return_fields=None):
		print>>sys.stderr, " \r\n GetPersons person_filter %s return_fields %s" %(person_filter,return_fields)
		if not self.person_list :
			print>>sys.stderr, " \r\n ========>GetPersons NO PERSON LIST DAMMIT<========== \r\n" 
			
		if not (person_filter or return_fields):
			return self.person_list
		
		return_person_list= []	
		return_person_list = parse_filter(self.person_list,person_filter ,'persons', return_fields)
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
	