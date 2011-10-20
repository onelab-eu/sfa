#!/usr/bin/python
#
##
# Import PLC records into the SFA database. It is indended that this tool be
# run once to create SFA records that reflect the current state of the
# planetlab database.
#
# The import tool assumes that the existing PLC hierarchy should all be part
# of "planetlab.us" (see the root_auth and level1_auth variables below).
#
# Public keys are extracted from the users' SSH keys automatically and used to
# create GIDs. This is relatively experimental as a custom tool had to be
# written to perform conversion from SSH to OpenSSL format. It only supports
# RSA keys at this time, not DSA keys.
##

import getopt
import sys
import tempfile


from sfa.util.record import *
from sfa.util.table import SfaTable
from sfa.util.xrn import get_leaf, get_authority
from sfa.util.plxrn import hostname_to_hrn, slicename_to_hrn, email_to_hrn, hrn_to_pl_slicename
from sfa.util.config import Config
from sfa.trust.certificate import convert_public_key, Keypair
from sfa.trust.trustedroots import *
from sfa.trust.hierarchy import *
from sfa.util.xrn import Xrn
from sfa.trust.gid import create_uuid


from sfa.senslab.SenslabImportUsers import *
from sfa.senslab.OARrestapi import *

from sfa.senslab.SenslabImport import SenslabImport





oarserver = {}
oarserver['ip'] = '10.127.255.254'
oarserver['port'] = 80
oarserver['uri'] = '/oarapi/resources/full.json'


def process_options():

   (options, args) = getopt.getopt(sys.argv[1:], '', [])
   for opt in options:
       name = opt[0]
       val = opt[1]


def load_keys(filename):
    keys = {}
    tmp_dict = {}
    try:
        execfile(filename, tmp_dict)
        if 'keys' in tmp_dict:
            keys = tmp_dict['keys']
        return keys
    except:
        return keys

def save_keys(filename, keys):
    f = open(filename, 'w')
    f.write("keys = %s" % str(keys))
    f.close()

def main():

    process_options()
    config = Config()
    if not config.SFA_REGISTRY_ENABLED:
        sys.exit(0)
    root_auth = config.SFA_REGISTRY_ROOT_AUTH
    interface_hrn = config.SFA_INTERFACE_HRN
    print interface_hrn, root_auth
    keys_filename = config.config_path + os.sep + 'person_keys.py' 

    sfaImporter = SenslabImport()
    SenslabUsers = SenslabImportUsers()
    
    OARImporter = OARapi()
    #print '\r\n =====OAR Importer list===== '
    #for node in OARImporter.OARserver.GetNodes().keys():
	#print node, OARImporter.OARserver.GetNodes[node]


    #if config.SFA_API_DEBUG: sfaImporter.logger.setLevelDebug()
    #shell = sfaImporter.shell
    #plc_auth = sfaImporter.plc_auth 
    #print plc_auth 

    # initialize registry db table
    table = SfaTable()
    if not table.exists():
    	table.create()

    # create root authority 
    sfaImporter.create_top_level_auth_records(root_auth)
    if not root_auth == interface_hrn:
       sfaImporter.create_top_level_auth_records(interface_hrn)
       
    # create interface records ADDED 12 JUILLET 2011 
    sfaImporter.logger.info("Import: creating interface records")
    sfaImporter.create_interface_records()

    # add local root authority's cert  to trusted list ADDED 12 JUILLET 2011 
    sfaImporter.logger.info("Import: adding " + interface_hrn + " to trusted list")
    authority = sfaImporter.AuthHierarchy.get_auth_info(interface_hrn)
    sfaImporter.TrustedRoots.add_gid(authority.get_gid_object())
    
    
    print "\r\n \r\n create dict of all existing sfa records"
 # create dict of all existing sfa records
    existing_records = {}
    existing_hrns = []
    key_ids = []
    person_keys = {} 
    results = table.find()
    for result in results:
        existing_records[(result['hrn'], result['type'])] = result
        existing_hrns.append(result['hrn'])   
     



    #Get Senslab nodes 
    nodes_dict  = OARImporter.GetNodes()
    print "\r\n NODES8DICT ",nodes_dict
    
    persons_list = SenslabUsers.GetPersons()
    print "\r\n PERSONS_LIST ",persons_list

    keys_list = SenslabUsers.GetKeys()
    print "\r\n KEYSS_LIST ",keys_list
    
    slices_list = SenslabUsers.GetSlices()
    print "\r\n SLICES_LIST ",slices_list
    
        # Get all Senslab sites
    sites_dict  = OARImporter.GetSites()
    print "\r\n sSITES_DICT" , sites_dict
    
 # start importing 
    for site in sites_dict:
        site_hrn = interface_hrn + "." + site['login_base']
        #sfa_logger().info("Importing site: %s" % site_hrn)
	print "HRN %s %s site existing in hrn ? %s" %( site['login_base'],site_hrn, site_hrn in existing_hrns)
        # import if hrn is not in list of existing hrns or if the hrn exists
        # but its not a site record
        if site_hrn not in existing_hrns or \
            (site_hrn, 'authority') not in existing_records:
             print "SITE HRN UNKNOWN" , site, site_hrn
             site_hrn = sfaImporter.import_site(interface_hrn, site)
	     
 	print "\r\n \r\n ===========IMPORT NODE_RECORDS ==========\r\n site %s \r\n \t nodes_dict %s" %(site,nodes_dict)	         
        # import node records
    	for node_id in site['node_ids']:
		#for[node['node_id'] for node in nodes_dict]:
			#print '\r\n \t **NODE_ID %s node %s '%( node_id, node)		
 			#continue 
		for node in nodes_dict:
			if node_id is node['node_id']:	
				#node = nodes_dict[node_id]
				print '\r\n \t NODE_ID %s node %s '%( node_id, node)
				hrn =  hostname_to_hrn(interface_hrn, site['login_base'], node['hostname'])
				break	

    		if hrn not in existing_hrns or \
    		(hrn, 'node') not in existing_records:
			print "\t\t NODE HRN NOT in existing records!" ,hrn
    			sfaImporter.import_node(hrn, node)

   # import persons
	for person in persons_list:
		hrn = email_to_hrn(site_hrn, person['email'])
		print >>sys.stderr, "\r\n\r\n^^^^^^^^^^^^^PERSON hrn %s person %s site hrn %s" %(hrn,person,site_hrn)    
		sfaImporter.import_person( site_hrn, person,keys_list)
		
# import slices
        for slice_id in site['slice_ids']:
		print >>sys.stderr, "\r\n\r\n \t ^^^^^^^\\\\\\\\\\\\\\\^^^^^^ slice_id  %s  " %(slice_id)    		
		for sl in slices_list:
			if slice_id is sl['slice_id']:
				#hrn = slicename_to_hrn(interface_hrn, sl['name'])
				hrn = email_to_hrn(site_hrn, sl['name'])
				print >>sys.stderr, "\r\n\r\n^^^^^^^^^^^^^SLICE ID hrn %s  site_hrn %s" %(hrn,site_hrn)    				
				if hrn not in existing_hrns or \
				(hrn, 'slice') not in existing_records:
					sfaImporter.import_slice(site_hrn, sl)	

					
					
 # remove stale records    
    for (record_hrn, type) in existing_records.keys():
        record = existing_records[(record_hrn, type)]
	print" \r\n ****record hrn %s \t\t TYPE %s " %(record_hrn,type)
        # if this is the interface name dont do anything
        if record_hrn == interface_hrn or \
           record_hrn == root_auth or \
           record['peer_authority']:
            continue


        found = False
        
        if type == 'authority':    
            for site in sites_dict:
		print "\t type : authority : ", site
                site_hrn = interface_hrn + "." + site['login_base']
                if site_hrn == record_hrn and site['site_id'] == record['pointer']:
                    found = True
                    print "\t \t Found :", found
                    break
 
        elif type == 'node':
            login_base = get_leaf(get_authority(record_hrn))

            nodename = Xrn.unescape(get_leaf(record_hrn))
            print "type: node : login_base %s nodename %s" %(login_base, nodename)
            if login_base in sites_dict:
		site = sites_dict[login_base]
		print "\t type node : login base %s site %s" %(login_base, site)
                for node in nodes_dict.values():
                    tmp_nodename = node['hostname']
                    if tmp_nodename == nodename and \
                       node['site_id'] == site['site_id'] and \
                       node['node_id'] == record['pointer']:
                        found = True
			print "\t Nodename: %s site id %s node id %s record %s" %( nodename,  node['site_id'], node['node_id'],record['pointer'])
                        break  
        else:
            continue 
        
        if not found:
            record_object = existing_records[(record_hrn, type)]
            print "\t\t NOT FOUND ! "
            sfaImporter.delete_record(record_hrn, type) 
                                   
    # save pub keys
    sfaImporter.logger.info('Import: saving current pub keys')
    save_keys(keys_filename, person_keys)                

 
  
if __name__ == "__main__":
    main()
