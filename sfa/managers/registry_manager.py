import types
import time 
# for get_key_from_incoming_ip
import tempfile
import os
import commands

from sfa.util.faults import RecordNotFound, AccountNotEnabled, PermissionError, MissingAuthority, \
    UnknownSfaType, ExistingRecord, NonExistingRecord
from sfa.util.prefixTree import prefixTree
from sfa.util.xrn import Xrn, get_authority, hrn_to_urn, urn_to_hrn
from sfa.util.plxrn import hrn_to_pl_login_base
from sfa.util.version import version_core
from sfa.util.sfalogging import logger

from sfa.trust.gid import GID 
from sfa.trust.credential import Credential
from sfa.trust.certificate import Certificate, Keypair, convert_public_key
from sfa.trust.gid import create_uuid

from sfa.storage.record import SfaRecord
from sfa.storage.table import SfaTable

class RegistryManager:

    def __init__ (self, config): pass

    # The GENI GetVersion call
    def GetVersion(self, api, options):
        peers = dict ( [ (hrn,interface.get_url()) for (hrn,interface) in api.registries.iteritems() 
                       if hrn != api.hrn])
        xrn=Xrn(api.hrn)
        return version_core({'interface':'registry',
                             'hrn':xrn.get_hrn(),
                             'urn':xrn.get_urn(),
                             'peers':peers})
    
    def GetCredential(self, api, xrn, type, is_self=False):
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
        self.driver.augment_records_with_testbed_info (record)
        if not self.driver.is_enabled (record):
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
    
    
    def Resolve(self, api, xrns, type=None, full=True):
    
        if not isinstance(xrns, types.ListType):
            xrns = [xrns]
            # try to infer type if not set and we get a single input
            if not type:
                type = Xrn(xrns).get_type()
        hrns = [urn_to_hrn(xrn)[0] for xrn in xrns] 
        # load all known registry names into a prefix tree and attempt to find
        # the longest matching prefix
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
                server_proxy = api.server_proxy(interface, credential)
                peer_records = server_proxy.Resolve(xrns, credential)
                records.extend([SfaRecord(dict=record).as_dict() for record in peer_records])
    
        # try resolving the remaining unfound records at the local registry
        local_hrns = list ( set(hrns).difference([record['hrn'] for record in records]) )
        # 
        table = SfaTable()
        local_records = table.findObjects({'hrn': local_hrns})
        
        if full:
            # in full mode we get as much info as we can, which involves contacting the 
            # testbed for getting implementation details about the record
            self.driver.augment_records_with_testbed_info(local_records)
            # also we fill the 'url' field for known authorities
            # used to be in the driver code, sounds like a poorman thing though
            def solve_neighbour_url (record):
                if not record['type'].startswith('authority'): return 
                hrn=record['hrn']
                for neighbour_dict in [ api.aggregates, api.registries ]:
                    if hrn in neighbour_dict:
                        record['url']=neighbour_dict[hrn].get_url()
                        return 
            [ solve_neighbour_url (record) for record in local_records ]
                    
        
        
        # convert local record objects to dicts
        records.extend([dict(record) for record in local_records])
        if type:
            records = filter(lambda rec: rec['type'] in [type], records)
    
        if not records:
            raise RecordNotFound(str(hrns))
    
        return records
    
    def List(self, api, xrn, origin_hrn=None):
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
            server_proxy = api.server_proxy(interface, credential)
            record_list = server_proxy.List(xrn, credential)
            records = [SfaRecord(dict=record).as_dict() for record in record_list]
        
        # if we still have not found the record yet, try the local registry
        if not records:
            if not api.auth.hierarchy.auth_exists(hrn):
                raise MissingAuthority(hrn)
    
            table = SfaTable()
            records = table.find({'authority': hrn})
    
        return records
    
    
    def CreateGid(self, api, xrn, cert):
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
    
    ####################
    # utility for handling relationships among the SFA objects 
    # given that the SFA db does not handle this sort of relationsships
    # it will rely on side-effects in the testbed to keep this persistent
    
    # subject_record describes the subject of the relationships
    # ref_record contains the target values for the various relationships we need to manage
    # (to begin with, this is just the slice x person relationship)
    def update_relations (self, subject_record, ref_record):
        type=subject_record['type']
        if type=='slice':
            self.update_relation(subject_record, 'researcher', ref_record.get('researcher'), 'user')
        
    # field_key is the name of one field in the record, typically 'researcher' for a 'slice' record
    # hrns is the list of hrns that should be linked to the subject from now on
    # target_type would be e.g. 'user' in the 'slice' x 'researcher' example
    def update_relation (self, sfa_record, field_key, hrns, target_type):
        # locate the linked objects in our db
        subject_type=sfa_record['type']
        subject_id=sfa_record['pointer']
        table = SfaTable()
        link_sfa_records = table.find ({'type':target_type, 'hrn': hrns})
        link_ids = [ rec.get('pointer') for rec in link_sfa_records ]
        self.driver.update_relation (subject_type, target_type, subject_id, link_ids)
        

    def Register(self, api, record):
    
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
        auth_info = api.auth.get_auth_info(record['authority'])
        pub_key = None
        # make sure record has a gid
        if 'gid' not in record:
            uuid = create_uuid()
            pkey = Keypair(create=True)
            if 'keys' in record and record['keys']:
                pub_key=record['keys']
                # use only first key in record
                if isinstance(record['keys'], types.ListType):
                    pub_key = record['keys'][0]
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

        # update testbed-specific data if needed
        pointer = self.driver.register (record, hrn, pub_key)

        record.set_pointer(pointer)
        record_id = table.insert(record)
        record['record_id'] = record_id
    
        # update membership for researchers, pis, owners, operators
        self.update_relations (record, record)
        
        return record.get_gid_object().save_to_string(save_parents=True)
    
    def Update(self, api, record_dict):
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
    
        # validate the type
        if type not in ['authority', 'slice', 'node', 'user']:
            raise UnknownSfaType(type) 

        # Use the pointer from the existing record, not the one that the user
        # gave us. This prevents the user from inserting a forged pointer
        pointer = record['pointer']
    
        # is the a change in keys ?
        new_key=None
        if type=='user':
            if 'keys' in new_record and new_record['keys']:
                new_key=new_record['keys']
                if isinstance (new_key,types.ListType):
                    new_key=new_key[0]

        # update the PLC information that was specified with the record
        if not self.driver.update (record, new_record, hrn, new_key):
            logger.warning("driver.update failed")
    
        # take new_key into account
        if new_key:
            # update the openssl key and gid
            pkey = convert_public_key(new_key)
            uuid = create_uuid()
            gid_object = api.auth.hierarchy.create_gid(urn, uuid, pkey)
            gid = gid_object.save_to_string(save_parents=True)
            record['gid'] = gid
            record = SfaRecord(dict=record)
            table.update(record)
        
        # update membership for researchers, pis, owners, operators
        self.update_relations (record, new_record)
        
        return 1 
    
    # expecting an Xrn instance
    def Remove(self, api, xrn, origin_hrn=None):
    
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
        
        if type not in ['slice', 'user', 'node', 'authority'] :
            raise UnknownSfaType(type)

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

        # call testbed callback first
        # IIUC this is done on the local testbed TOO because of the refreshpeer link
        if not self.driver.remove(record):
            logger.warning("driver.remove failed")

        # delete from sfa db
        table.remove(record)
    
        return 1

    # This is a PLC-specific thing...
    def get_key_from_incoming_ip (self, api):
        # verify that the callers's ip address exist in the db and is an interface
        # for a node in the db
        (ip, port) = api.remote_addr
        interfaces = self.driver.shell.GetInterfaces({'ip': ip}, ['node_id'])
        if not interfaces:
            raise NonExistingRecord("no such ip %(ip)s" % locals())
        nodes = self.driver.shell.GetNodes([interfaces[0]['node_id']], ['node_id', 'hostname'])
        if not nodes:
            raise NonExistingRecord("no such node using ip %(ip)s" % locals())
        node = nodes[0]
       
        # look up the sfa record
        table = SfaTable()
        records = table.findObjects({'type': 'node', 'pointer': node['node_id']})
        if not records:
            raise RecordNotFound("pointer:" + str(node['node_id']))  
        record = records[0]
        
        # generate a new keypair and gid
        uuid = create_uuid()
        pkey = Keypair(create=True)
        urn = hrn_to_urn(record['hrn'], record['type'])
        gid_object = api.auth.hierarchy.create_gid(urn, uuid, pkey)
        gid = gid_object.save_to_string(save_parents=True)
        record['gid'] = gid
        record.set_gid(gid)

        # update the record
        table.update(record)
  
        # attempt the scp the key
        # and gid onto the node
        # this will only work for planetlab based components
        (kfd, key_filename) = tempfile.mkstemp() 
        (gfd, gid_filename) = tempfile.mkstemp() 
        pkey.save_to_file(key_filename)
        gid_object.save_to_file(gid_filename, save_parents=True)
        host = node['hostname']
        key_dest="/etc/sfa/node.key"
        gid_dest="/etc/sfa/node.gid" 
        scp = "/usr/bin/scp" 
        #identity = "/etc/planetlab/root_ssh_key.rsa"
        identity = "/etc/sfa/root_ssh_key"
        scp_options=" -i %(identity)s " % locals()
        scp_options+="-o StrictHostKeyChecking=no " % locals()
        scp_key_command="%(scp)s %(scp_options)s %(key_filename)s root@%(host)s:%(key_dest)s" %\
                         locals()
        scp_gid_command="%(scp)s %(scp_options)s %(gid_filename)s root@%(host)s:%(gid_dest)s" %\
                         locals()    

        all_commands = [scp_key_command, scp_gid_command]
        
        for command in all_commands:
            (status, output) = commands.getstatusoutput(command)
            if status:
                raise Exception, output

        for filename in [key_filename, gid_filename]:
            os.unlink(filename)

        return 1 
