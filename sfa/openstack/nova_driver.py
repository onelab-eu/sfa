import time
import datetime

from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
    RecordNotFound, SfaNotImplemented, SliverDoesNotExist, \
    SfaInvalidArgument

from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf, urn_to_sliver_id
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename, hrn_to_os_tenant_name
from sfa.util.cache import Cache
from sfa.trust.credential import Credential
# used to be used in get_ticket
#from sfa.trust.sfaticket import SfaTicket

from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver
from sfa.openstack.shell import Shell
from sfa.openstack.osaggregate import OSAggregate
from sfa.planetlab.plslices import PlSlices

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict ( [ (rec[key],rec) for rec in recs ] )

#
# PlShell is just an xmlrpc serverproxy where methods
# can be sent as-is; it takes care of authentication
# from the global config
# 
class NovaDriver(Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, config):
        Driver.__init__(self, config)
        self.shell = Shell(config)
        self.cache=None
        if config.SFA_AGGREGATE_CACHING:
            if NovaDriver.cache is None:
                NovaDriver.cache = Cache()
            self.cache = NovaDriver.cache
 
    ########################################
    ########## registry oriented
    ########################################

    ########## disabled users 
    def is_enabled (self, record):
        # all records are enabled
        return True

    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        
        if sfa_record['type'] == 'slice':
            record = self.register_slice(sfa_record, hrn)         
        elif sfa_record['type'] == 'user':
            record = self.register_user(sfa_record, hrn, pub_key)
        elif sfa_record['type'].startswith('authority'): 
            record = self.register_authority(sfa_record, hrn)
        # We should be returning the records id as a pointer but
        # this is a string and the records table expects this to be an 
        # int.
        #return record.id
        return -1

    def register_slice(self, sfa_record, hrn):
        # add slice description, name, researchers, PI
        name = hrn_to_os_tenant_name(hrn)
        description = sfa_record.get('description', None)
        self.shell.auth_manager.tenants.create(name, description)
        tenant = self.shell.auth_manager.tenants.find(name=name)
        auth_hrn = OSXrn(xrn=hrn, type='slice').get_authority_hrn()
        parent_tenant_name = OSXrn(xrn=auth_hrn, type='slice').get_tenant_name()
        parent_tenant = self.shell.auth_manager.tenants.find(name=parent_tenant_name)
        researchers = sfa_record.get('researchers', [])
        for researcher in researchers:
            name = Xrn(researcher).get_leaf()
            user = self.shell.auth_manager.users.find(name=name)
            self.shell.auth_manager.roles.add_user_role(user, 'user', tenant)

        pis = sfa_record.get('pis', [])
        for pi in pis:
            name = Xrn(pi).get_leaf()
            user = self.shell.auth_manager.users.find(name=name)
            self.shell.auth_manager.roles.add_user_role(user, 'pi', tenant)
            self.shell.auth_manager.roles.add_user_role(user, 'pi', parent_tenant)

        return tenant
       
    def register_user(self, sfa_record, hrn, pub_key):
        # add person roles, projects and keys
        email = sfa_record.get('email', None)
        xrn = Xrn(hrn)
        name = xrn.get_leaf()
        auth_hrn = xrn.get_authority_hrn()
        tenant_name = OSXrn(xrn=auth_hrn, type='authority').get_tenant_name()  
        tenant = self.shell.auth_manager.tenants.find(name=tenant_name)  
        self.shell.auth_manager.users.create(name, email=email, tenant_id=tenant.id)
        user = self.shell.auth_manager.users.find(name=name)
        slices = sfa_records.get('slices', [])
        for slice in projects:
            slice_tenant_name = OSXrn(xrn=slice, type='slice').get_tenant_name()
            slice_tenant = self.shell.auth_manager.tenants.find(name=slice_tenant_name)
            self.shell.auth_manager.roles.add_user_role(user, slice_tenant, 'user')
        keys = sfa_records.get('keys', [])
        for key in keys:
            keyname = OSXrn(xrn=hrn, type='user').get_slicename()
            self.shell.nova_client.keypairs.create(keyname, key)
        return user

    def register_authority(self, sfa_record, hrn):
        name = OSXrn(xrn=hrn, type='authority').get_tenant_name()
        self.shell.auth_manager.tenants.create(name, sfa_record.get('description', ''))
        tenant = self.shell.auth_manager.tenants.find(name=name)
        return tenant
        
        
    ##########
    # xxx actually old_sfa_record comes filled with plc stuff as well in the original code
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        type = new_sfa_record['type'] 
        
        # new_key implemented for users only
        if new_key and type not in [ 'user' ]:
            raise UnknownSfaType(type)

        elif type == "slice":
            # can update project manager and description
            name = hrn_to_os_slicename(hrn)
            researchers = sfa_record.get('researchers', [])
            pis = sfa_record.get('pis', [])
            project_manager = None
            description = sfa_record.get('description', None)
            if pis:
                project_manager = Xrn(pis[0], 'user').get_leaf()
            elif researchers:
                project_manager = Xrn(researchers[0], 'user').get_leaf()
            self.shell.auth_manager.modify_project(name, project_manager, description)

        elif type == "user":
            # can techinally update access_key and secret_key,
            # but that is not in our scope, so we do nothing.  
            pass
        return True
        

    ##########
    def remove (self, sfa_record):
        type=sfa_record['type']
        if type == 'user':
            name = Xrn(sfa_record['hrn']).get_leaf()     
            if self.shell.auth_manager.get_user(name):
                self.shell.auth_manager.delete_user(name)
        elif type == 'slice':
            name = hrn_to_os_slicename(sfa_record['hrn'])     
            if self.shell.auth_manager.get_project(name):
                self.shell.auth_manager.delete_project(name)
        return True


    ####################
    def fill_record_info(self, records):
        """
        Given a (list of) SFA record, fill in the PLC specific 
        and SFA specific fields in the record. 
        """
        if not isinstance(records, list):
            records = [records]

        for record in records:
            if record['type'] == 'user':
                record = self.fill_user_record_info(record)
            elif record['type'] == 'slice':
                record = self.fill_slice_record_info(record)
            elif record['type'].startswith('authority'):
                record = self.fill_auth_record_info(record)
            else:
                continue
            record['geni_urn'] = hrn_to_urn(record['hrn'], record['type'])
            record['geni_certificate'] = record['gid'] 
            #if os_record.created_at is not None:    
            #    record['date_created'] = datetime_to_string(utcparse(os_record.created_at))
            #if os_record.updated_at is not None:
            #    record['last_updated'] = datetime_to_string(utcparse(os_record.updated_at))
 
        return records

    def fill_user_record_info(self, record):
        xrn = Xrn(record['hrn'])
        name = xrn.get_leaf()
        record['name'] = name
        user = self.shell.auth_manager.users.find(name=name)
        record['email'] = user.email
        tenant = self.shell.auth_manager.tenants.find(id=user.tenantId)
        slices = []
        all_tenants = self.shell.auth_manager.tenants.list()
        for tmp_tenant in all_tenants:
            if tmp_tenant.name.startswith(tenant.name +"."):
                for tmp_user in tmp_tenant.list_users():
                    if tmp_user.name == user.name:
                        slice_hrn = ".".join([self.hrn, tmp_tenant.name]) 
                        slices.append(slice_hrn)   
        record['slices'] = slices
        roles = self.shell.auth_manager.roles.roles_for_user(user, tenant)
        record['roles'] = [role.name for role in roles] 
        keys = self.shell.nova_manager.keypairs.findall(name=record['hrn'])
        record['keys'] = [key.public_key for key in keys]
        return record

    def fill_slice_record_info(self, record):
        tenant_name = hrn_to_os_tenant_name(record['hrn'])
        tenant = self.shell.auth_manager.tenants.find(name=tenant_name)
        parent_tenant_name = OSXrn(xrn=tenant_name).get_authority_hrn()
        parent_tenant = self.shell.auth_manager.tenants.find(name=parent_tenant_name)
        researchers = []
        pis = []

        # look for users and pis in slice tenant
        for user in tenant.list_users():
            for role in self.shell.auth_manager.roles.roles_for_user(user, tenant):
                if role.name.lower() == 'pi':
                    user_tenant = self.shell.auth_manager.tenants.find(id=user.tenantId)
                    hrn = ".".join([self.hrn, user_tenant.name, user.name])
                    pis.append(hrn)
                elif role.name.lower() in ['user', 'member']:
                    user_tenant = self.shell.auth_manager.tenants.find(id=user.tenantId)
                    hrn = ".".join([self.hrn, user_tenant.name, user.name])
                    researchers.append(hrn)

        # look for pis in the slice's parent (site/organization) tenant
        for user in parent_tenant.list_users():
            for role in self.shell.auth_manager.roles.roles_for_user(user, parent_tenant):
                if role.name.lower() == 'pi':
                    user_tenant = self.shell.auth_manager.tenants.find(id=user.tenantId)
                    hrn = ".".join([self.hrn, user_tenant.name, user.name])
                    pis.append(hrn)
        record['name'] = tenant_name
        record['description'] = tenant.description
        record['PI'] = pis
        if pis:
            record['geni_creator'] = pis[0]
        else:
            record['geni_creator'] = None
        record['researcher'] = researchers
        return record

    def fill_auth_record_info(self, record):
        tenant_name = hrn_to_os_tenant_name(record['hrn'])
        tenant = self.shell.auth_manager.tenants.find(name=tenant_name)
        researchers = []
        pis = []

        # look for users and pis in slice tenant
        for user in tenant.list_users():
            for role in self.shell.auth_manager.roles.roles_for_user(user, tenant):
                hrn = ".".join([self.hrn, tenant.name, user.name])
                if role.name.lower() == 'pi':
                    pis.append(hrn)
                elif role.name.lower() in ['user', 'member']:
                    researchers.append(hrn)

        # look for slices
        slices = []
        all_tenants = self.shell.auth_manager.tenants.list() 
        for tmp_tenant in all_tenants:
            if tmp_tenant.name.startswith(tenant.name+"."):
                slices.append(".".join([self.hrn, tmp_tenant.name])) 

        record['name'] = tenant_name
        record['description'] = tenant.description
        record['PI'] = pis
        record['enabled'] = tenant.enabled
        record['researchers'] = researchers
        record['slices'] = slices
        return record

    ####################
    # plcapi works by changes, compute what needs to be added/deleted
    def update_relation (self, subject_type, target_type, subject_id, target_ids):
        # hard-wire the code for slice/user for now, could be smarter if needed
        if subject_type =='slice' and target_type == 'user':
            subject=self.shell.project_get(subject_id)[0]
            current_target_ids = [user.name for user in subject.members]
            add_target_ids = list ( set (target_ids).difference(current_target_ids))
            del_target_ids = list ( set (current_target_ids).difference(target_ids))
            logger.debug ("subject_id = %s (type=%s)"%(subject_id,type(subject_id)))
            for target_id in add_target_ids:
                self.shell.project_add_member(target_id,subject_id)
                logger.debug ("add_target_id = %s (type=%s)"%(target_id,type(target_id)))
            for target_id in del_target_ids:
                logger.debug ("del_target_id = %s (type=%s)"%(target_id,type(target_id)))
                self.shell.project_remove_member(target_id, subject_id)
        else:
            logger.info('unexpected relation to maintain, %s -> %s'%(subject_type,target_type))

        
    ########################################
    ########## aggregate oriented
    ########################################

    def testbed_name (self): return "openstack"

    # 'geni_request_rspec_versions' and 'geni_ad_rspec_versions' are mandatory
    def aggregate_version (self):
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict()) 
        return {
            'testbed':self.testbed_name(),
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions,
            }

    def list_slices (self, creds, options):
        # look in cache first
        if self.cache:
            slices = self.cache.get('slices')
            if slices:
                logger.debug("OpenStackDriver.list_slices returns from cache")
                return slices
    
        # get data from db
        instance_urns = []
        instances = self.shell.nova_manager.servers.findall()
        for instance in instances:
            if instance.name not in instance_urns:
                instance_urns.append(OSXrn(instance.name, type='slice').urn)

        # cache the result
        if self.cache:
            logger.debug ("OpenStackDriver.list_slices stores value in cache")
            self.cache.add('slices', instance_urns) 
    
        return instance_urns
        
    # first 2 args are None in case of resource discovery
    def list_resources (self, slice_urn, slice_hrn, creds, options):
        cached_requested = options.get('cached', True) 
    
        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_"+options.get('info', 'default')
    
        # look in cache first
        if cached_requested and self.cache and not slice_hrn:
            rspec = self.cache.get(version_string)
            if rspec:
                logger.debug("OpenStackDriver.ListResources: returning cached advertisement")
                return rspec 
    
        #panos: passing user-defined options
        #print "manager options = ",options
        aggregate = OSAggregate(self)
        rspec =  aggregate.get_rspec(slice_xrn=slice_urn, version=rspec_version, 
                                     options=options)
    
        # cache the result
        if self.cache and not slice_hrn:
            logger.debug("OpenStackDriver.ListResources: stores advertisement in cache")
            self.cache.add(version_string, rspec)
    
        return rspec
    
    def sliver_status (self, slice_urn, slice_hrn):
        # find out where this slice is currently running
        project_name = hrn_to_os_slicename(slice_hrn)
        instances = self.shell.nova_manager.servers.findall(name=project_name)
        if len(instances) == 0:
            raise SliverDoesNotExist("You have not allocated any slivers here") 
        
        result = {}
        top_level_status = 'unknown'
        if instances:
            top_level_status = 'ready'
        result['geni_urn'] = slice_urn
        result['plos_login'] = 'root'
        # do we need real dates here? 
        result['plos_expires'] = None
        result['geni_expires'] = None
        
        resources = []
        for instance in instances:
            res = {}
            # instances are accessed by ip, not hostname. We need to report the ip
            # somewhere so users know where to ssh to.     
            res['geni_expires'] = None
            #res['plos_hostname'] = instance.hostname
            res['plos_created_at'] = datetime_to_string(utcparse(instance.created))    
            res['plos_boot_state'] = instance.status
            res['plos_sliver_type'] = self.shell.nova_manager.flavors.find(id=instance.flavor['id']).name 
            sliver_id =  Xrn(slice_urn).get_sliver_id(instance.id)
            res['geni_urn'] = sliver_id

            if instance.status.lower() == 'active':
                res['boot_state'] = 'ready'
                res['geni_status'] = 'ready'
            else:
                res['boot_state'] = 'unknown'  
                res['geni_status'] = 'unknown'
            resources.append(res)
            
        result['geni_status'] = top_level_status
        result['geni_resources'] = resources
        return result

    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):

        aggregate = OSAggregate(self)
        rspec = RSpec(rspec_string)
        instance_name = hrn_to_os_slicename(slice_hrn)
       
        # assume first user is the caller and use their context
        # for the ec2/euca api connection. Also, use the first users
        # key as the project key.
        key_name = None
        if len(users) > 1:
            key_name = aggregate.create_instance_key(slice_hrn, users[0])

        # collect public keys
        pubkeys = []
        for user in users:
            pubkeys.extend(user['keys'])
           
        aggregate.run_instances(instance_name, rspec_string, key_name, pubkeys)    
   
        return aggregate.get_rspec(slice_xrn=slice_urn, version=rspec.version)

    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        aggregate = OSAggregate(self)
        project_name = hrn_to_os_slicename(slice_hrn)
        return aggregate.delete_instances(project_name)   

    def update_sliver(self, slice_urn, slice_hrn, rspec, creds, options):
        name = hrn_to_os_slicename(slice_hrn)
        aggregate = OSAggregate(self)
        return aggregate.update_instances(name)
    
    def renew_sliver (self, slice_urn, slice_hrn, creds, expiration_time, options):
        return True

    def start_slice (self, slice_urn, slice_hrn, creds):
        return 1

    def stop_slice (self, slice_urn, slice_hrn, creds):
        name = OSXrn(xrn=slice_urn).name
        aggregate = OSAggregate(self)
        return aggregate.stop_instances(name) 

    def reset_slice (self, slice_urn, slice_hrn, creds):
        raise SfaNotImplemented ("reset_slice not available at this interface")
    
    # xxx this code is quite old and has not run for ages
    # it is obviously totally broken and needs a rewrite
    def get_ticket (self, slice_urn, slice_hrn, creds, rspec_string, options):
        raise SfaNotImplemented,"OpenStackDriver.get_ticket needs a rewrite"
# please keep this code for future reference
#        slices = PlSlices(self)
#        peer = slices.get_peer(slice_hrn)
#        sfa_peer = slices.get_sfa_peer(slice_hrn)
#    
#        # get the slice record
#        credential = api.getCredential()
#        interface = api.registries[api.hrn]
#        registry = api.server_proxy(interface, credential)
#        records = registry.Resolve(xrn, credential)
#    
#        # make sure we get a local slice record
#        record = None
#        for tmp_record in records:
#            if tmp_record['type'] == 'slice' and \
#               not tmp_record['peer_authority']:
#    #Error (E0602, GetTicket): Undefined variable 'SliceRecord'
#                slice_record = SliceRecord(dict=tmp_record)
#        if not record:
#            raise RecordNotFound(slice_hrn)
#        
#        # similar to CreateSliver, we must verify that the required records exist
#        # at this aggregate before we can issue a ticket
#        # parse rspec
#        rspec = RSpec(rspec_string)
#        requested_attributes = rspec.version.get_slice_attributes()
#    
#        # ensure site record exists
#        site = slices.verify_site(slice_hrn, slice_record, peer, sfa_peer)
#        # ensure slice record exists
#        slice = slices.verify_slice(slice_hrn, slice_record, peer, sfa_peer)
#        # ensure person records exists
#    # xxx users is undefined in this context
#        persons = slices.verify_persons(slice_hrn, slice, users, peer, sfa_peer)
#        # ensure slice attributes exists
#        slices.verify_slice_attributes(slice, requested_attributes)
#        
#        # get sliver info
#        slivers = slices.get_slivers(slice_hrn)
#    
#        if not slivers:
#            raise SliverDoesNotExist(slice_hrn)
#    
#        # get initscripts
#        initscripts = []
#        data = {
#            'timestamp': int(time.time()),
#            'initscripts': initscripts,
#            'slivers': slivers
#        }
#    
#        # create the ticket
#        object_gid = record.get_gid_object()
#        new_ticket = SfaTicket(subject = object_gid.get_subject())
#        new_ticket.set_gid_caller(api.auth.client_gid)
#        new_ticket.set_gid_object(object_gid)
#        new_ticket.set_issuer(key=api.key, subject=self.hrn)
#        new_ticket.set_pubkey(object_gid.get_pubkey())
#        new_ticket.set_attributes(data)
#        new_ticket.set_rspec(rspec)
#        #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
#        new_ticket.encode()
#        new_ticket.sign()
#    
#        return new_ticket.save_to_string(save_parents=True)
