import types
import time 
import sys

from sfa.util.faults import *
from sfa.util.prefixTree import prefixTree
from sfa.util.record import SfaRecord
from sfa.senslab.table_slab import SfaTable
from sfa.util.record import SfaRecord
from sfa.trust.gid import GID 
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import hrn_to_pl_login_base
from sfa.trust.credential import Credential
from sfa.trust.certificate import Certificate, Keypair
from sfa.trust.gid import create_uuid
from sfa.util.version import version_core
from sfa.senslab.api import *

myapi=SfaAPI(interface='registry')
# The GENI GetVersion call
def GetVersion(api):
    
    peers =dict ([ (peername,v._ServerProxy__host) for (peername,v) in myapi.registries.iteritems() 
                   if peername != myapi.hrn])
    xrn=Xrn(myapi.hrn)
    return version_core({'interface':'registry',
                         'hrn':xrn.get_hrn(),
                         'urn':xrn.get_urn(),
                         'peers':peers})

def get_credential(api, xrn, type, is_self=False):
    # convert xrn to hrn     
    if type:
        hrn = urn_to_hrn(xrn)[0]
    else:
        hrn, type = urn_to_hrn(xrn)

    # Is this a root or sub authority
    auth_hrn = myapi.auth.get_authority(hrn)
    print>> sys.stderr , " \r\n        REGISTRY get_credential auth_hrn:" , auth_hrn,"hrn : ", hrn, " Type : ", type, "is self : " , is_self,"<<"
    if not auth_hrn or hrn == myapi.config.SFA_INTERFACE_HRN:
        auth_hrn = hrn
    # get record info
    auth_info = myapi.auth.get_auth_info(auth_hrn)
    table = SfaTable()
    print >> sys.stderr , " findObject ", type, hrn
    records = table.findObjects({'type': type, 'hrn': hrn})
    print>> sys.stderr , " \r\n    ++    REGISTRY get_credential hrn %s records %s " %(hrn, records)      
    if not records:
        raise RecordNotFound(hrn)
    record = records[0]

    # verify_cancreate_credential requires that the member lists
    # (researchers, pis, etc) be filled in
    myapi.fill_record_info(record)
    record['enabled'] = True
    print>> sys.stderr , " \r\n    ++    REGISTRY get_credential hrn %s record['enabled'] %s is_self %s" %(hrn, record['enabled'], is_self)    
    if record['type']=='user':
       if not record['enabled']:
          print>> sys.stderr , " \r\n    ++    REGISTRY get_credential hrn %s ACCOUNT Not enabled"
          raise AccountNotEnabled(": PlanetLab account %s is not enabled. Please contact your site PI" %(record['email']))

    # get the callers gid
    # if this is a self cred the record's gid is the caller's gid
    if is_self:
        caller_hrn = hrn
        caller_gid = record.get_gid_object()
	print>>sys.stderr, " \r\n REGISTRY IS SELF OK caller_hrn %s--- \r\n caller_gid %s---------" %(caller_hrn,caller_gid)
    else:
	print>> sys.stderr , " \r\n    ++  ELSE   "     
        caller_gid = myapi.auth.client_cred.get_gid_caller() 
	print>> sys.stderr , " \r\n    ++  ELSE  caller_gid %s record %s" %(caller_gid, record)	
        caller_hrn = caller_gid.get_hrn()
  	print>> sys.stderr , " \r\n    ++  ELSE  caller_hrn %s " %(caller_hrn)
		  
    object_hrn = record.get_gid_object().get_hrn()
    print>> sys.stderr , " \r\n    ++  ELSE object_hrn  %s " %(object_hrn)
	
    rights = myapi.auth.determine_user_rights(caller_hrn, record)
    print>> sys.stderr , " \r\n    ++  After rights record: %s \r\n ====RIGHTS %s  " %(record , rights)
     
    # make sure caller has rights to this object
    if rights.is_empty():
        raise PermissionError(caller_hrn + " has no rights to " + record['name'])

    object_gid = GID(string=record['gid'])
    new_cred = Credential(subject = object_gid.get_subject())
    new_cred.set_gid_caller(caller_gid)
    new_cred.set_gid_object(object_gid)
    new_cred.set_issuer_keys(auth_info.get_privkey_filename(), auth_info.get_gid_filename())
    #new_cred.set_pubkey(object_gid.get_pubkey())
    new_cred.set_privileges(rights)
    new_cred.get_privileges().delegate_all_privileges(True)
    if 'expires' in record:
        new_cred.set_expiration(int(record['expires']))
    auth_kind = "authority,ma,sa"
    # Parent not necessary, verify with certs
    #new_cred.set_parent(myapi.auth.hierarchy.get_auth_cred(auth_hrn, kind=auth_kind))
    new_cred.encode()
    new_cred.sign()

    return new_cred.save_to_string(save_parents=True)


def resolve(api, xrns, type=None, full=True):

    # load all known registry names into a prefix tree and attempt to find
    # the longest matching prefix 
    print >>sys.stderr , '\t\t REGISTRY MANAGER : resolve=========xrns ', xrns
    if not isinstance(xrns, types.ListType):
        if not type:
            type = Xrn(xrns).get_type()
        xrns = [xrns]
    hrns = [urn_to_hrn(xrn)[0] for xrn in xrns] 
    print >>sys.stderr , '\t\t =========hrns ', hrns
    # create a dict where key is a registry hrn and its value is a
    # hrns at that registry (determined by the known prefix tree).  
    xrn_dict = {}
    print >>sys.stderr, '\r\n REGISTRY MANAGER : resolve xrns '  , xrns #api.__dict__.keys()
    registries = myapi.registries
    tree = prefixTree()
    registry_hrns = registries.keys()
    print >>sys.stderr, '\r\n \t\t REGISTRY MANAGER registry_hrns'  , registry_hrns
    tree.load(registry_hrns)
    for xrn in xrns:
        registry_hrn = tree.best_match(urn_to_hrn(xrn)[0])
	print >>sys.stderr, '\t\tREGISTRY MANAGER  *****tree.best_match ', registry_hrn
        if registry_hrn not in xrn_dict:
            xrn_dict[registry_hrn] = []
        xrn_dict[registry_hrn].append(xrn)
	print >>sys.stderr, '\t\tREGISTRY MANAGER  *****xrn_dict[registry_hrn] ',xrn_dict[registry_hrn]
    records = [] 

    for registry_hrn in xrn_dict:
        # skip the hrn without a registry hrn
        # XX should we let the user know the authority is unknown?   
	print >>sys.stderr, '\t\t registry_hrn in xrn_dict ', registry_hrn    
        if not registry_hrn:
            continue

        # if the best match (longest matching hrn) is not the local registry,
        # forward the request
        xrns = xrn_dict[registry_hrn]
        if registry_hrn != myapi.hrn:
            credential = myapi.getCredential()
            peer_records = registries[registry_hrn].Resolve(xrns, credential)
            print >>sys.stderr , '\t\t peer_records ', peer_records
            records.extend([SfaRecord(dict=record).as_dict() for record in peer_records])

    print >>sys.stderr,'\t\t hrns ' , hrns
    # try resolving the remaining unfound records at the local registry
    remaining_hrns = set(hrns).difference([record['hrn'] for record in records])

    # convert set to list
    remaining_hrns = [hrn for hrn in remaining_hrns] 
    print >>sys.stderr, '\t\t remaining_hrns', remaining_hrns
    table = SfaTable()
    local_records = table.findObjects({'hrn': remaining_hrns})

    print >>sys.stderr, '\t\t LOCAL REC !', local_records  
    for rec in local_records:
        print >>sys.stderr, '\t\t resolve regmanager : rec ', rec    
                   
    if full:
	print >>sys.stderr, '\r\n \r\n REGISTRY:_FULL', myapi     
        myapi.fill_record_info(local_records)
	
  
    # convert local record objects to dicts
    records.extend([dict(record) for record in local_records])
    print >>sys.stderr, "\r\n \t\t records extends %s" %(records)      
    if not records:
        raise RecordNotFound(str(hrns))

    if type:
        records = filter(lambda rec: rec['type'] in [type], records)

    return records

def list(api, xrn, origin_hrn=None):
    hrn, type = urn_to_hrn(xrn)
    # load all know registry names into a prefix tree and attempt to find
    # the longest matching prefix
    records = []
    registries = myapi.registries
    registry_hrns = registries.keys()
    tree = prefixTree()
    tree.load(registry_hrns)
    registry_hrn = tree.best_match(hrn)
   
    #if there was no match then this record belongs to an unknow registry
    if not registry_hrn:
        raise MissingAuthority(xrn)
    
    # if the best match (longest matching hrn) is not the local registry,
    # forward the request
    records = []    
    if registry_hrn != myapi.hrn:
        credential = myapi.getCredential()
	print>>sys.stderr, "Registries : ", registries
        #record_list = registries[registry_hrn].List(xrn, credential)
	
	interface=registries[registries_hrn]
	server=api.get_server(interface,credential)
	records= server.List(xrn,credential)
	
        records = [SfaRecord(dict=record).as_dict() for record in record_list]
    
    # if we still have not found the record yet, try the local registry
    if not records:
        if not myapi.auth.hierarchy.auth_exists(hrn):
            raise MissingAuthority(hrn)

        table = SfaTable()
        records = table.find({'authority': hrn})

    return records


def register(api, record):

    hrn = str(record['hrn']).strip("['']")
    type_of_rec = str( record['type']).strip("['']")
  
 
    urn = hrn_to_urn(hrn,type_of_rec)
    # validate the type
 
    if type_of_rec not in ['authority', 'slice', 'node', 'user']:
        raise UnknownSfaType(type_of_rec) 
    
    # check if record already exists
    table = SfaTable()
    existing_records = table.find({'type': type_of_rec, 'hrn': hrn})
    if existing_records:
        raise ExistingRecord(hrn)
       
    record = SfaRecord(dict = record)

    print>>sys.stderr, " \r\n \r\n ----------- REGISTRY_MANAGER_SLAN.PY  register  SfaRecordrecord %s" %(record)
    #record['authority'] = get_authority(record['hrn'])
    record['authority'] = get_authority(hrn)
    
    #type_of_rec = record['type']
    #hrn = record['hrn']
    
    #api.auth.verify_object_permission(hrn)
    myapi.auth.verify_object_permission( record['hrn'])
    auth_info = myapi.auth.get_auth_info(record['authority'])
  
    

    pub_key = None
    # make sure record has a gid
    if 'gid' not in record:
        uuid = create_uuid()
        pkey = Keypair(create=True)
        if 'key' in record and record['key']:
            if isinstance(record['key'], types.ListType):
                pub_key = record['key'][0]
            else:
                pub_key = record['key']
            pkey = convert_public_key(pub_key)

        gid_object = myapi.auth.hierarchy.create_gid(urn, uuid, pkey)
        gid = gid_object.save_to_string(save_parents=True)
        record['gid'] = gid
        record.set_gid(gid)
	print>>sys.stderr, " \r\n \r\n ----------- REGISTRY_MANAGER_SLAB.PY   record['gid']  %s" %(record['gid'])   
	print>>sys.stderr, " \r\n \r\n ----------- REGISTRY_MANAGER_SLAB.PY  register type_of_rec %s"%(type_of_rec)
	
    if type_of_rec in ["authority"]:	

        # update the tree
        if not myapi.auth.hierarchy.auth_exists(hrn):
            myapi.auth.hierarchy.create_auth(hrn_to_urn(hrn,'authority'))

        # get the GID from the newly created authority
        gid = auth_info.get_gid_object()
        record.set_gid(gid.save_to_string(save_parents=True))
	
        #pl_record = myapi.sfa_fields_to_pl_fields(type, hrn, record)
	print>>sys.stderr, " \r\n \r\n ----------- REGISTRY_MANAGER_SLAB.PY  register : type_of_rec in [authority ] sfa_fields_to_pl_fields FIELDS A CHANGER"    
	
        sites = myapi.oar.GetSites( [pl_record['login_base']])
        if not sites:
            pointer = myapi.oar.AddSite( pl_record)
        else:
            pointer = sites[0]['site_id']

        record.set_pointer(pointer)
        record['pointer'] = pointer

    elif (type_of_rec == "slice"):
        acceptable_fields=['url', 'instantiation', 'name', 'description']
        pl_record = myapi.sfa_fields_to_pl_fields(type_of_rec, hrn, record)
	print>>sys.stderr, " \r\n \r\n ----------- REGISTRY_MANAGER_SLAB.PY  register  slice pl_record %s"%(pl_record)
        for key in pl_record.keys():
            if key not in acceptable_fields:
                pl_record.pop(key)
        slices = myapi.users.GetSlices( [pl_record['name']])
        if not slices:
             pointer = myapi.users.AddSlice(pl_record)
        else:
             pointer = slices[0]['slice_id']
        record.set_pointer(pointer)
        record['pointer'] = pointer

    elif  (type_of_rec == "user"):
        persons = myapi.users.GetPersons( [record['email']]) 
	if not persons:
           print>>sys.stderr, "  \r\n \r\n ----------- registry_manager_slab  register NO PERSON ADD TO LDAP?"
      
        #if not persons:
            #pointer = myapi.users.AddPerson( dict(record))
        #else:
            #pointer = persons[0]['person_id']

        if 'enabled' in record and record['enabled']:
            myapi.users.UpdatePerson( pointer, {'enabled': record['enabled']})
        # add this persons to the site only if he is being added for the first
        # time by sfa and doesont already exist in plc
        if not persons or not persons[0]['site_ids']:
            login_base = get_leaf(record['authority'])
            myapi.users.AddPersonToSite( pointer, login_base)

        # What roles should this user have?
        myapi.users.AddRoleToPerson( 'user', pointer)
        # Add the user's key
        if pub_key:
            myapi.users.AddPersonKey( pointer, {'key_type' : 'ssh', 'key' : pub_key})

    #elif (type == "node"):
        #pl_record = myapi.sfa_fields_to_pl_fields(type, hrn, record)
        #login_base = hrn_to_pl_login_base(record['authority'])
        #nodes = myapi.oar.GetNodes( [pl_record['hostname']])
        #if not nodes:
            #pointer = myapi.oar.AddNode(login_base, pl_record)
        #else:
            #pointer = nodes[0]['node_id']

    ##record['pointer'] = pointer
    ##record.set_pointer(pointer)
    #record_id = table.insert(record)
    #record['record_id'] = record_id

    # update membership for researchers, pis, owners, operators
    myapi.update_membership(None, record)

    return record.get_gid_object().save_to_string(save_parents=True)

def update(api, record_dict):
    new_record = SfaRecord(dict = record_dict)
    type = new_record['type']
    hrn = new_record['hrn']
    urn = hrn_to_urn(hrn,type)
    myapi.auth.verify_object_permission(hrn)
    table = SfaTable()
    # make sure the record exists
    records = table.findObjects({'type': type, 'hrn': hrn})
    if not records:
        raise RecordNotFound(hrn)
    record = records[0]
    record['last_updated'] = time.gmtime()

    # Update_membership needs the membership lists in the existing record
    # filled in, so it can see if members were added or removed
    myapi.fill_record_info(record)

    # Use the pointer from the existing record, not the one that the user
    # gave us. This prevents the user from inserting a forged pointer
    pointer = record['pointer']
    # update the PLC information that was specified with the record

    if (type == "authority"):
        myapi.oar.UpdateSite( pointer, new_record)

    elif type == "slice":
        pl_record=myapi.sfa_fields_to_pl_fields(type, hrn, new_record)
        if 'name' in pl_record:
            pl_record.pop('name')
            myapi.users.UpdateSlice( pointer, pl_record)

    elif type == "user":
        # SMBAKER: UpdatePerson only allows a limited set of fields to be
        #    updated. Ideally we should have a more generic way of doing
        #    this. I copied the field names from UpdatePerson.py...
        update_fields = {}
        all_fields = new_record
        for key in all_fields.keys():
            if key in ['first_name', 'last_name', 'title', 'email',
                       'password', 'phone', 'url', 'bio', 'accepted_aup',
                       'enabled']:
                update_fields[key] = all_fields[key]
        myapi.users.UpdatePerson( pointer, update_fields)

        if 'key' in new_record and new_record['key']:
            # must check this key against the previous one if it exists
            persons = myapi.users.GetPersons( [pointer], ['key_ids'])
            person = persons[0]
            keys = person['key_ids']
            keys = myapi.users.GetKeys( person['key_ids'])
            key_exists = False
            if isinstance(new_record['key'], types.ListType):
                new_key = new_record['key'][0]
            else:
                new_key = new_record['key']
            
            # Delete all stale keys
            for key in keys:
                if new_record['key'] != key['key']:
                    myapi.users.DeleteKey( key['key_id'])
                else:
                    key_exists = True
            if not key_exists:
                myapi.users.AddPersonKey( pointer, {'key_type': 'ssh', 'key': new_key})

            # update the openssl key and gid
            pkey = convert_public_key(new_key)
            uuid = create_uuid()
            gid_object = myapi.auth.hierarchy.create_gid(urn, uuid, pkey)
            gid = gid_object.save_to_string(save_parents=True)
            record['gid'] = gid
            record = SfaRecord(dict=record)
            table.update(record)

    elif type == "node":
        myapi.oar.UpdateNode( pointer, new_record)

    else:
        raise UnknownSfaType(type)

    # update membership for researchers, pis, owners, operators
    myapi.update_membership(record, new_record)
    
    return 1 

# expecting an Xrn instance
def remove(api, xrn, origin_hrn=None):

    table = SfaTable()
    filter = {'hrn': xrn.get_hrn()}
    hrn=xrn.get_hrn()
    type=xrn.get_type()
    if type and type not in ['all', '*']:
        filter['type'] = type

    records = table.find(filter)
    if not records: raise RecordNotFound(hrn)
    record = records[0]
    type = record['type']

    credential = myapi.getCredential()
    registries = myapi.registries

    # Try to remove the object from the PLCDB of federated agg.
    # This is attempted before removing the object from the local agg's PLCDB and sfa table
    if hrn.startswith(myapi.hrn) and type in ['user', 'slice', 'authority']:
        for registry in registries:
            if registry not in [myapi.hrn]:
                try:
                    result=registries[registry].remove_peer_object(credential, record, origin_hrn)
                except:
                    pass
    if type == "user":
        persons = myapi.users.GetPersons(record['pointer'])
        # only delete this person if he has site ids. if he doesnt, it probably means
        # he was just removed from a site, not actually deleted
        if persons and persons[0]['site_ids']:
            myapi.users.DeletePerson(record['pointer'])
    elif type == "slice":
        if myapi.users.GetSlices( record['pointer']):
            myapi.users.DeleteSlice( record['pointer'])
    elif type == "node":
        if myapi.oar.GetNodes( record['pointer']):
            myapi.oar.DeleteNode( record['pointer'])
    elif type == "authority":
        if myapi.oar.GetSites( record['pointer']):
            myapi.oar.DeleteSite( record['pointer'])
    else:
        raise UnknownSfaType(type)

    table.remove(record)

    return 1

def remove_peer_object(api, record, origin_hrn=None):
    pass

def register_peer_object(api, record, origin_hrn=None):
    pass
