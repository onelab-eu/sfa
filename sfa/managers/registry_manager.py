import types
import time 

from sfa.util.faults import RecordNotFound, AccountNotEnabled, PermissionError, MissingAuthority, \
    UnknownSfaType, ExistingRecord
from sfa.util.prefixTree import prefixTree
from sfa.util.record import SfaRecord
from sfa.util.table import SfaTable
from sfa.util.xrn import Xrn, get_leaf, get_authority, hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import hrn_to_pl_login_base
from sfa.util.version import version_core

from sfa.trust.gid import GID 
from sfa.trust.credential import Credential
from sfa.trust.certificate import Certificate, Keypair, convert_public_key
from sfa.trust.gid import create_uuid

# The GENI GetVersion call
def GetVersion(api):
    peers =dict ([ (peername,v._ServerProxy__host) for (peername,v) in api.registries.iteritems() 
                   if peername != api.hrn])
    xrn=Xrn(api.hrn)
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
    auth_hrn = api.auth.get_authority(hrn)
    if not auth_hrn or hrn == api.config.SFA_INTERFACE_HRN:
        auth_hrn = hrn
    # get record info
    auth_info = api.auth.get_auth_info(auth_hrn)
    table = SfaTable()
    records = table.findObjects({'type': type, 'hrn': hrn})
    if not records:
        raise RecordNotFound(hrn)
    record = records[0]

    # verify_cancreate_credential requires that the member lists
    # (researchers, pis, etc) be filled in
    api.driver.fill_record_info(record, api.aggregates)
    if record['type']=='user':
       if not record['enabled']:
          raise AccountNotEnabled(": PlanetLab account %s is not enabled. Please contact your site PI" %(record['email']))

    # get the callers gid
    # if this is a self cred the record's gid is the caller's gid
    if is_self:
        caller_hrn = hrn
        caller_gid = record.get_gid_object()
    else:
        caller_gid = api.auth.client_cred.get_gid_caller() 
        caller_hrn = caller_gid.get_hrn()
    
    object_hrn = record.get_gid_object().get_hrn()
    rights = api.auth.determine_user_rights(caller_hrn, record)
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
    #new_cred.set_parent(api.auth.hierarchy.get_auth_cred(auth_hrn, kind=auth_kind))
    new_cred.encode()
    new_cred.sign()

    return new_cred.save_to_string(save_parents=True)


def resolve(api, xrns, type=None, full=True):

    # load all known registry names into a prefix tree and attempt to find
    # the longest matching prefix
    if not isinstance(xrns, types.ListType):
        if not type:
            type = Xrn(xrns).get_type()
        xrns = [xrns]
    hrns = [urn_to_hrn(xrn)[0] for xrn in xrns] 
    # create a dict where key is a registry hrn and its value is a
    # hrns at that registry (determined by the known prefix tree).  
    xrn_dict = {}
    registries = api.registries
    tree = prefixTree()
    registry_hrns = registries.keys()
    tree.load(registry_hrns)
    for xrn in xrns:
        registry_hrn = tree.best_match(urn_to_hrn(xrn)[0])
        if registry_hrn not in xrn_dict:
            xrn_dict[registry_hrn] = []
        xrn_dict[registry_hrn].append(xrn)
        
    records = [] 
    for registry_hrn in xrn_dict:
        # skip the hrn without a registry hrn
        # XX should we let the user know the authority is unknown?       
        if not registry_hrn:
            continue

        # if the best match (longest matching hrn) is not the local registry,
        # forward the request
        xrns = xrn_dict[registry_hrn]
        if registry_hrn != api.hrn:
            credential = api.getCredential()
            interface = api.registries[registry_hrn]
            server = api.server_proxy(interface, credential)
            peer_records = server.Resolve(xrns, credential)
            records.extend([SfaRecord(dict=record).as_dict() for record in peer_records])

    # try resolving the remaining unfound records at the local registry
    remaining_hrns = set(hrns).difference([record['hrn'] for record in records])
    # convert set to list
    remaining_hrns = [hrn for hrn in remaining_hrns] 
    table = SfaTable()
    local_records = table.findObjects({'hrn': remaining_hrns})
    if full:
        api.driver.fill_record_info(local_records, api.aggregates)
    
    # convert local record objects to dicts
    records.extend([dict(record) for record in local_records])
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
    registries = api.registries
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
    if registry_hrn != api.hrn:
        credential = api.getCredential()
        interface = api.registries[registry_hrn]
        server = api.server_proxy(interface, credential)
        record_list = server.List(xrn, credential)
        records = [SfaRecord(dict=record).as_dict() for record in record_list]
    
    # if we still have not found the record yet, try the local registry
    if not records:
        if not api.auth.hierarchy.auth_exists(hrn):
            raise MissingAuthority(hrn)

        table = SfaTable()
        records = table.find({'authority': hrn})

    return records


def create_gid(api, xrn, cert):
    # get the authority
    authority = Xrn(xrn=xrn).get_authority_hrn()
    auth_info = api.auth.get_auth_info(authority)
    if not cert:
        pkey = Keypair(create=True)
    else:
        certificate = Certificate(string=cert)
        pkey = certificate.get_pubkey()    
    gid = api.auth.hierarchy.create_gid(xrn, create_uuid(), pkey) 
    return gid.save_to_string(save_parents=True)
    
def register(api, record):

    hrn, type = record['hrn'], record['type']
    urn = hrn_to_urn(hrn,type)
    # validate the type
    if type not in ['authority', 'slice', 'node', 'user']:
        raise UnknownSfaType(type) 
    
    # check if record already exists
    table = SfaTable()
    existing_records = table.find({'type': type, 'hrn': hrn})
    if existing_records:
        raise ExistingRecord(hrn)
       
    record = SfaRecord(dict = record)
    record['authority'] = get_authority(record['hrn'])
    type = record['type']
    hrn = record['hrn']
    auth_info = api.auth.get_auth_info(record['authority'])
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

        gid_object = api.auth.hierarchy.create_gid(urn, uuid, pkey)
        gid = gid_object.save_to_string(save_parents=True)
        record['gid'] = gid
        record.set_gid(gid)

    if type in ["authority"]:
        # update the tree
        if not api.auth.hierarchy.auth_exists(hrn):
            api.auth.hierarchy.create_auth(hrn_to_urn(hrn,'authority'))

        # get the GID from the newly created authority
        gid = auth_info.get_gid_object()
        record.set_gid(gid.save_to_string(save_parents=True))
        pl_record = api.driver.sfa_fields_to_pl_fields(type, hrn, record)
        sites = api.driver.GetSites([pl_record['login_base']])
        if not sites:
            pointer = api.driver.AddSite(pl_record)
        else:
            pointer = sites[0]['site_id']

        record.set_pointer(pointer)
        record['pointer'] = pointer

    elif (type == "slice"):
        acceptable_fields=['url', 'instantiation', 'name', 'description']
        pl_record = api.driver.sfa_fields_to_pl_fields(type, hrn, record)
        for key in pl_record.keys():
            if key not in acceptable_fields:
                pl_record.pop(key)
        slices = api.driver.GetSlices([pl_record['name']])
        if not slices:
             pointer = api.driver.AddSlice(pl_record)
        else:
             pointer = slices[0]['slice_id']
        record.set_pointer(pointer)
        record['pointer'] = pointer

    elif  (type == "user"):
        persons = api.driver.GetPersons([record['email']])
        if not persons:
            pointer = api.driver.AddPerson(dict(record))
        else:
            pointer = persons[0]['person_id']

        if 'enabled' in record and record['enabled']:
            api.driver.UpdatePerson(pointer, {'enabled': record['enabled']})
        # add this persons to the site only if he is being added for the first
        # time by sfa and doesont already exist in plc
        if not persons or not persons[0]['site_ids']:
            login_base = get_leaf(record['authority'])
            api.driver.AddPersonToSite(pointer, login_base)

        # What roles should this user have?
        api.driver.AddRoleToPerson('user', pointer)
        # Add the user's key
        if pub_key:
            api.driver.AddPersonKey(pointer, {'key_type' : 'ssh', 'key' : pub_key})

    elif (type == "node"):
        pl_record = api.driver.sfa_fields_to_pl_fields(type, hrn, record)
        login_base = hrn_to_pl_login_base(record['authority'])
        nodes = api.driver.GetNodes([pl_record['hostname']])
        if not nodes:
            pointer = api.driver.AddNode(login_base, pl_record)
        else:
            pointer = nodes[0]['node_id']

    record['pointer'] = pointer
    record.set_pointer(pointer)
    record_id = table.insert(record)
    record['record_id'] = record_id

    # update membership for researchers, pis, owners, operators
    api.driver.update_membership(None, record)

    return record.get_gid_object().save_to_string(save_parents=True)

def update(api, record_dict):
    new_record = SfaRecord(dict = record_dict)
    type = new_record['type']
    hrn = new_record['hrn']
    urn = hrn_to_urn(hrn,type)
    table = SfaTable()
    # make sure the record exists
    records = table.findObjects({'type': type, 'hrn': hrn})
    if not records:
        raise RecordNotFound(hrn)
    record = records[0]
    record['last_updated'] = time.gmtime()

    # Update_membership needs the membership lists in the existing record
    # filled in, so it can see if members were added or removed
    api.driver.fill_record_info(record, api.aggregates)

    # Use the pointer from the existing record, not the one that the user
    # gave us. This prevents the user from inserting a forged pointer
    pointer = record['pointer']
    # update the PLC information that was specified with the record

    if (type == "authority"):
        api.driver.UpdateSite(pointer, new_record)

    elif type == "slice":
        pl_record=api.driver.sfa_fields_to_pl_fields(type, hrn, new_record)
        if 'name' in pl_record:
            pl_record.pop('name')
            api.driver.UpdateSlice(pointer, pl_record)

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
        api.driver.UpdatePerson(pointer, update_fields)

        if 'key' in new_record and new_record['key']:
            # must check this key against the previous one if it exists
            persons = api.driver.GetPersons([pointer], ['key_ids'])
            person = persons[0]
            keys = person['key_ids']
            keys = api.driver.GetKeys(person['key_ids'])
            key_exists = False
            if isinstance(new_record['key'], types.ListType):
                new_key = new_record['key'][0]
            else:
                new_key = new_record['key']
            
            # Delete all stale keys
            for key in keys:
                if new_record['key'] != key['key']:
                    api.driver.DeleteKey(key['key_id'])
                else:
                    key_exists = True
            if not key_exists:
                api.driver.AddPersonKey(pointer, {'key_type': 'ssh', 'key': new_key})

            # update the openssl key and gid
            pkey = convert_public_key(new_key)
            uuid = create_uuid()
            gid_object = api.auth.hierarchy.create_gid(urn, uuid, pkey)
            gid = gid_object.save_to_string(save_parents=True)
            record['gid'] = gid
            record = SfaRecord(dict=record)
            table.update(record)

    elif type == "node":
        api.driver.UpdateNode(pointer, new_record)

    else:
        raise UnknownSfaType(type)

    # update membership for researchers, pis, owners, operators
    api.driver.update_membership(record, new_record)
    
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

    credential = api.getCredential()
    registries = api.registries

    # Try to remove the object from the PLCDB of federated agg.
    # This is attempted before removing the object from the local agg's PLCDB and sfa table
    if hrn.startswith(api.hrn) and type in ['user', 'slice', 'authority']:
        for registry in registries:
            if registry not in [api.hrn]:
                try:
                    result=registries[registry].remove_peer_object(credential, record, origin_hrn)
                except:
                    pass
    if type == "user":
        persons = api.driver.GetPersons(record['pointer'])
        # only delete this person if he has site ids. if he doesnt, it probably means
        # he was just removed from a site, not actually deleted
        if persons and persons[0]['site_ids']:
            api.driver.DeletePerson(record['pointer'])
    elif type == "slice":
        if api.driver.GetSlices(record['pointer']):
            api.driver.DeleteSlice(record['pointer'])
    elif type == "node":
        if api.driver.GetNodes(record['pointer']):
            api.driver.DeleteNode(record['pointer'])
    elif type == "authority":
        if api.driver.GetSites(record['pointer']):
            api.driver.DeleteSite(record['pointer'])
    else:
        raise UnknownSfaType(type)

    table.remove(record)

    return 1

def remove_peer_object(api, record, origin_hrn=None):
    pass

def register_peer_object(api, record, origin_hrn=None):
    pass
