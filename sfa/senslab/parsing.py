
import sys
import httplib
import json
from collections import defaultdict

def strip_dictionnary (dict_to_strip):
	stripped_filter = []
	stripped_filterdict = {} 
	for f in dict_to_strip :
		stripped_filter.append(str(f).strip('|'))
		
	stripped_filterdict = dict(zip(stripped_filter, dict_to_strip.values()))
	
	return stripped_filterdict
	

def filter_return_fields( dict_to_filter, return_fields):
	filtered_dict = {}
	for field in return_fields:
		if field in dict_to_filter:
			filtered_dict[field] = dict_to_filter[field]
	return filtered_dict
	
	
	
def parse_filter(list_to_filter, param_filter, type_of_list, return_fields=None) :
	list_type = { 'persons': {'str': 'hrn','int':'record_id'},\
	 'keys':{'int':'key_id'},\
	 'site':{'str':'login_base','int':'site_id'},\
	  'node':{'str':'hostname','int':'node_id'},\
	  'slice':{'str':'slice_hrn','int':'record_id_slice'},\
          'peers':{'str':'hrn'}}
        	
	if  param_filter is None and return_fields is None:
            return list_to_filter
        
	if type_of_list not in list_type:
		return []

	return_filtered_list= []
	
	for item in list_to_filter:
		tmp_item = {}
		
		if type(param_filter) is list :
			
			for p_filter in param_filter:
				if type(p_filter) is int:
					if item[list_type[type_of_list]['int']] == p_filter :
						if return_fields:
							tmp_item = filter_return_fields(item,return_fields)
						else:
							tmp_item = item
						return_filtered_list.append(tmp_item)
					
				if type(p_filter) is str:
					if item[list_type[type_of_list]['str']] == str(p_filter) :
						if return_fields:
							tmp_item = filter_return_fields(item,return_fields)
						else:
							tmp_item = item
						return_filtered_list.append(tmp_item)
					
	
		elif type(param_filter) is dict:
			#stripped_filterdict = strip_dictionnary(param_filter)
			#tmp_copy = {}
			#tmp_copy = item.copy()
			#key_list = tmp_copy.keys()			
			#for key in key_list:
				#if key not in stripped_filterdict:
					#del tmp_copy[key] 
                                        
                        #rif the item matches the filter, returns it
                        founditem = []
                        check =  [ True for  k in param_filter.keys() if 'id' in k ]
                        dflt= defaultdict(str,param_filter)
                              
                        
                        
                        #founditem =  [ item for k in dflt if item[k] in dflt[k]]
                        for k in dflt:
                            if item[k] in dflt[k]:
                               founditem = [item]

                        if founditem: 
                            if return_fields:
                                tmp_item = filter_return_fields(founditem[0],return_fields)
                            else:
                                tmp_item = founditem[0]
                            return_filtered_list.append(tmp_item)
			
			
			#if cmp(tmp_copy, stripped_filterdict) == 0:	
				#if return_fields:
					#tmp_item = filter_return_fields(item,return_fields)
				#else:
					
					#tmp_item = item	
				#return_filtered_list.append(tmp_item)
	if return_filtered_list	:
	   return return_filtered_list
        