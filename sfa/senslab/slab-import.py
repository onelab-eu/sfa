
import sys
import datetime
import time
from sfa.senslab.OARrestapi import OARapi
from sfa.senslab.LDAPapi import LDAPapi
from sfa.senslab.slabdriver import SlabDriver
from sfa.senslab.slabpostgres import SlabDB
from sfa.util.config import Config
from sfa.util.plxrn import PlXrn
from sfa.util.xrn import hrn_to_urn, get_authority,Xrn,get_leaf
from sfa.util.table import SfaTable
from sfa.util.record import SfaRecord
from sfa.trust.hierarchy import Hierarchy
from sfa.trust.certificate import Keypair,convert_public_key
from sfa.trust.gid import create_uuid
from sfa.trust.trustedroots import TrustedRoots

config = Config()
TrustedR = TrustedRoots(Config.get_trustedroots_dir(config))
AuthHierarchy = Hierarchy()
table = SfaTable()
db = SlabDB()
if not table.exists():
    table.create()
    
    
def create_sm_client_record():
    """
    Create a user record for the Slicemanager service.
    """
    hrn = config.SFA_INTERFACE_HRN + '.slicemanager'
    urn = hrn_to_urn(hrn, 'user')
    if not AuthHierarchy.auth_exists(urn):
        AuthHierarchy.create_auth(urn)

    auth_info = AuthHierarchy.get_auth_info(hrn)
    table = SfaTable()
    sm_user_record = table.find({'type': 'user', 'hrn': hrn})
    if not sm_user_record:
        record = SfaRecord(hrn=hrn, gid=auth_info.get_gid_object(), type="user", pointer=-1)
        record['authority'] = get_authority(record['hrn'])
        table.insert(record)
                
def create_interface_records():
    """
    Create a record for each SFA interface
    """
    # just create certs for all sfa interfaces even if they
    # arent enabled
    interface_hrn = config.SFA_INTERFACE_HRN
    interfaces = ['authority+sa', 'authority+am', 'authority+sm']
    
    auth_info = AuthHierarchy.get_auth_info(interface_hrn)
    pkey = auth_info.get_pkey_object()
    for interface in interfaces:
        interface_record = table.find({'type': interface, 'hrn': interface_hrn})
        if not interface_record:
            urn = hrn_to_urn(interface_hrn, interface)
            gid = AuthHierarchy.create_gid(urn, create_uuid(), pkey)
            record = SfaRecord(hrn=interface_hrn, gid=gid, type=interface, pointer=-1)  
            record['authority'] = get_authority(interface_hrn)
            print>>sys.stderr,"\r\n ==========create_interface_records", record['authority']
            table.insert(record)                
                
def create_top_level_auth_records(hrn):
    """
    Create top level records (includes root and sub authorities (local/remote)
    """

    urn = hrn_to_urn(hrn, 'authority')
    # make sure parent exists
    parent_hrn = get_authority(hrn)
    print>>sys.stderr, "\r\n =========slab-import create_top_level_auth_records hrn %s  urn %s parent_hrn %s \r\n" %(hrn, urn, parent_hrn)
    if not parent_hrn:
        parent_hrn = hrn
    if not parent_hrn == hrn:
        create_top_level_auth_records(parent_hrn)

    # create the authority if it doesnt already exist 
    if not AuthHierarchy.auth_exists(urn):
        AuthHierarchy.create_auth(urn)
    
    # create the db record if it doesnt already exist    
    auth_info = AuthHierarchy.get_auth_info(hrn)
   
    auth_record = table.find({'type': 'authority', 'hrn': hrn})

    if not auth_record:
        auth_record = SfaRecord(hrn=hrn, gid=auth_info.get_gid_object(), type="authority", pointer=-1)
        auth_record['authority'] = get_authority(auth_record['hrn'])
        print sys.stderr, " \r\n \t slab-import : auth record %s inserted record %s " %(auth_record['hrn'], auth_record)
        table.insert(auth_record)

        
    
def import_node(hrn, node):

    # ASN.1 will have problems with hrn's longer than 64 characters
    if len(hrn) > 64:
        hrn = hrn[:64]

    node_record = table.find({'type': 'node', 'hrn': hrn})
    pkey = Keypair(create=True)        
    print>>sys.stderr, " \r\n \t slab-import : hrn %s" %(hrn )
    urn = hrn_to_urn(hrn, 'node')
    node_gid = AuthHierarchy.create_gid(urn, create_uuid(), pkey)
    node_record = SfaRecord(hrn=hrn, gid=node_gid, type="node", pointer=node['node_id'])
    node_record['authority'] = get_authority(node_record['hrn'])
    extime = datetime.datetime.utcnow()
    node_record['date_created'] = int(time.mktime(extime.timetuple()))
    existing_records = table.find({'hrn': hrn, 'type': 'node', 'pointer': node['node_id']})
    if not existing_records:
        print>>sys.stderr, " \r\n \t slab-import : node record %s inserted" %(node_record )
        table.insert(node_record)
    else:
        existing_record = existing_records[0]
        node_record['record_id'] = existing_record['record_id']
        table.update(node_record)

# person is already a sfa record 
def import_person(authname,person):       
    existing_records = table.find({'hrn': person['hrn'], 'type': 'user'})
    extime = datetime.datetime.utcnow()
    person['date_created'] = int(time.mktime(extime.timetuple()))

  
    if not existing_records:
        print>>sys.stderr, " \r\n \t slab-import : person record %s inserted" %(person['hrn'])
        uuid=create_uuid() 
        RSA_KEY_STRING=person['pkey']
        pkey=convert_public_key(RSA_KEY_STRING)
	person['gid']=AuthHierarchy.create_gid("urn:publicid:IDN+"+authname+"+user+"+person['uid'], uuid, pkey, CA=False).save_to_string()
        table.insert(person)
    else:
        existing_record = existing_records[0]
        person['record_id'] = existing_record['record_id']
        # handle key change ??? 
        table.update(person)
        
def import_slice(person):

    hrn = person['hrn']+'_slice'
    pkey = Keypair(create=True)
    urn = hrn_to_urn(hrn, 'slice')
    gid = AuthHierarchy.create_gid(urn, create_uuid(), pkey)
    slice_record= SfaRecord(hrn=hrn, gid=gid, type="slice", pointer=-1)
    slice_record['authority'] = get_authority(slice_record['hrn'])
   
    extime = datetime.datetime.utcnow()
    slice_record['date_created'] = int(time.mktime(extime.timetuple()))
    #special slice table for Senslab, to store nodes info (OAR) 			

    existing_records = table.find({'hrn': slice_record['hrn'], 'type': 'slice'})
    if not existing_records:
        print>>sys.stderr, " \r\n \t slab-import : slice record %s inserted" %(slice_record['hrn'])
        table.insert(slice_record)
        db.insert_slab_slice(person)

    else:
        print>>sys.stderr, " \r\n \t slab-import : slice record %s updated" %(slice_record['hrn'])
        existing_record = existing_records[0]
        slice_record['record_id'] = existing_record['record_id']
        table.update(slice_record)
        db.update_senslab_slice(slice_record)   
        
def delete_record( hrn, type):
    # delete the record
    record_list = table.find({'type': type, 'hrn': hrn})
    for record in record_list:
        print>>sys.stderr, " \r\n \t slab-import : record %s deleted" %(record['hrn'])
        table.remove(record)
                
def hostname_to_hrn(root_auth,login_base,hostname):
    return PlXrn(auth=auth,hostname=login_base+'_'+hostname).get_hrn()

    
def main():

    if not db.exists('slice'):
        db.createtable('slice')
        
    if not config.SFA_REGISTRY_ENABLED:
        sys.exit(0)
    root_auth = config.SFA_REGISTRY_ROOT_AUTH
    interface_hrn = config.SFA_INTERFACE_HRN
    print interface_hrn, root_auth
    
    #Get all records in the sfa table   
    # create dict of all existing sfa records
    existing_records = {}
    existing_hrns = []
    key_ids = []
    results = table.find()
   
    for result in results:
        existing_records[(result['hrn'], result['type'])] = result
        existing_hrns.append(result['hrn'])   
        
    # create root authority if it doesn't exist
    if root_auth not in  existing_hrns or \
    (root_auth, 'authority') not in existing_records:
        create_top_level_auth_records(root_auth)
        if not root_auth == interface_hrn:
            create_top_level_auth_records(interface_hrn)
    
        # create s user record for the slice manager Do we need this?
        create_sm_client_record()
        
        # create interface records ADDED 18 nov 11 Do we need this?
    
        create_interface_records()
    
        # add local root authority's cert  to trusted list ADDED 18 nov 11 Do we need this?
        
        authority = AuthHierarchy.get_auth_info(interface_hrn)
        TrustedR.add_gid(authority.get_gid_object())


    #Get Senslab nodes 
   
    Driver = SlabDriver(config)
    nodes_dict  = Driver.GetNodes()
    #print "\r\n NODES8DICT ",nodes_dict
    
    ldap_person_list = Driver.GetPersons()

        # import node records
    for node in nodes_dict:
        # Sandrine
        # A changer pour l utilisation du nouveau OAR de prod, le site etant contenu dans le hostname
        hrn =  hostname_to_hrn( root_auth,node['site_login_base'], node['hostname'])
        if hrn not in existing_hrns or \
        (hrn, 'node') not in existing_records:
            import_node(hrn, node)

   # import persons and slices
    for person in ldap_person_list:
        if person['hrn'] not in existing_hrns or \
            (person['hrn'], 'user') not in existing_records :
            import_person(root_auth,person)
            import_slice(person)
				
                                
    # remove stale records    
    system_records = [interface_hrn, root_auth, interface_hrn + '.slicemanager']

    for (record_hrn, type) in existing_records.keys():
        if record_hrn in system_records:
            continue
        
        record = existing_records[(record_hrn, type)]
        if record['peer_authority']:
            continue					



        found = False
        
        if type == 'authority':    
            found = True
            print "\t \t Found :", found
            break
                
        elif type == 'user':
            for person in ldap_person_list:
                if person['hrn'] == record_hrn:
                    found = True
                    break
            
        elif type == 'node':
            login_base = get_leaf(get_authority(record_hrn))
            nodename = Xrn.unescape(get_leaf(record_hrn))
            for node in nodes_dict:
                if node['hostname'] == nodename :
                    found = True
                    break 
                
        elif type == 'slice':
            for person in ldap_person_list:
                if person['hrn']+'_slice' == record_hrn:
                    found = True
                    break           
        else:
            continue 
        
        if not found:
            record_object = existing_records[(record_hrn, type)]
            print "\t\t  NOT FOUND ! ", record_hrn
            delete_record(record_hrn, type) 
    
if __name__ == "__main__":
    main()    
