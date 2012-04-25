
# import modules used here -- sys is a very standard one
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
	#print>>sys.stderr, " \r\n \t \tfilter_return_fields return fields %s " %(return_fields)
	for field in return_fields:
		#print>>sys.stderr, " \r\n \t \tfield %s " %(field)	
		if field in dict_to_filter:
			filtered_dict[field] = dict_to_filter[field]
	#print>>sys.stderr, " \r\n \t\t filter_return_fields filtered_dict %s " %(filtered_dict)
	return filtered_dict
	
	
	
def parse_filter(list_to_filter, param_filter, type_of_list, return_fields=None) :
	list_type = { 'persons': {'str': 'hrn','int':'record_id'},\
	 'keys':{'int':'key_id'},\
	 'site':{'str':'login_base','int':'site_id'},\
	  'node':{'str':'hostname','int':'node_id'},\
	  'slice':{'str':'slice_hrn','int':'record_id_slice'},\
          'peers':{'str':'hrn'}}
        	
	#print>>sys.stderr, " \r\n ___ parse_filter param_filter %s type %s  return fields %s " %(param_filter,type_of_list, return_fields)  
	if  param_filter is None and return_fields is None:
            return list_to_filter
        
	if type_of_list not in list_type:
		#print>>sys.stderr, " \r\n type_of_list Error  parse_filter %s " %(type_of_list)
		return []

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
					if item[list_type[type_of_list]['str']] == str(p_filter) :
                                                #print>>sys.stderr, " \r\n p_filter %s \t item %s "%(p_filter,item[list_type[type_of_list]['str']])
						if return_fields:
							tmp_item = filter_return_fields(item,return_fields)
						else:
							tmp_item = item
						return_filtered_list.append(tmp_item)
					#print>>sys.stderr, " \r\n 2tmp_item",tmp_item
					
	
		elif type(param_filter) is dict:
			#stripped_filterdict = strip_dictionnary(param_filter)
			#tmp_copy = {}
			#tmp_copy = item.copy()
			#print>>sys.stderr, " \r\n \t\t ________tmp_copy %s " %(tmp_copy)
			#key_list = tmp_copy.keys()			
			#for key in key_list:
				#print>>sys.stderr, " \r\n \t\t  key %s " %(key)
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
                                #print>>sys.stderr, "  \r\n \r\n parsing.py param_filter dflt %s founditem %s " %(dflt, founditem)
                                tmp_item = filter_return_fields(founditem[0],return_fields)
                            else:
                                tmp_item = founditem[0]
                            return_filtered_list.append(tmp_item)
			
			#print>>sys.stderr, " \r\n tmp_copy %s param_filter %s cmp = %s " %(tmp_copy, param_filter,cmp(tmp_copy, stripped_filterdict))
			
			#if cmp(tmp_copy, stripped_filterdict) == 0:	
				#if return_fields:
					#tmp_item = filter_return_fields(item,return_fields)
				#else:
					
					#tmp_item = item	
				#return_filtered_list.append(tmp_item)
	if return_filtered_list	:
	   return return_filtered_list
        