import time
import datetime
from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
     RecordNotFound, SfaNotImplemented, SfaInvalidArgument, UnsupportedOperation
from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf, get_authority 
from sfa.util.cache import Cache
from sfa.trust.credential import Credential
# used to be used in get_ticket
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec
from sfa.storage.model import RegRecord, SliverAllocation
# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename, hrn_to_os_tenant_name
from sfa.openstack.shell import Shell
from sfa.openstack.osaggregate import OSAggregate
from sfa.planetlab.plslices import PlSlices

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict([ (rec[key],rec) for rec in recs ])

#
# PlShell is just an xmlrpc serverproxy where methods
# can be sent as-is; it takes care of authentication
# from the global config
# 
class OpenstackDriver(Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__(self, api):
        Driver.__init__(self, api)
        config = api.config
        self.shell = Shell(config=config)
        self.cache=None
        if config.SFA_AGGREGATE_CACHING:
            if OpenstackDriver.cache is None:
                OpenstackDriver.cache = Cache()
            self.cache = OpenstackDriver.cache

    def sliver_to_slice_xrn(self, xrn):
        sliver_id_parts = Xrn(xrn).get_sliver_id_parts()
        slice = self.shell.auth_manager.tenants.find(id=sliver_id_parts[0])
        if not slice:
            raise Forbidden("Unable to locate slice record for sliver:  %s" % xrn)
        slice_xrn = OSXrn(name=slice.name, type='slice')
        return slice_xrn

    def check_sliver_credentials(self, creds, urns):
        # build list of cred object hrns
        slice_cred_names = []
        for cred in creds:
            slice_cred_hrn = Credential(cred=cred).get_gid_object().get_hrn()
            slice_cred_names.append(OSXrn(xrn=slice_cred_hrn).get_slicename())

        # look up slice name of slivers listed in urns arg
        slice_ids = []
        for urn in urns:
            sliver_id_parts = Xrn(xrn=urn).get_sliver_id_parts()
            slice_ids.append(sliver_id_parts[0])

        if not slice_ids:
             raise Forbidden("sliver urn not provided")

        sliver_names = []
        for slice_id in slice_ids:
            slice = self.shell.auth_manager.tenants.find(slice_id) 
            sliver_names.append(slice['name'])

        # make sure we have a credential for every specified sliver ierd
        for sliver_name in sliver_names:
            if sliver_name not in slice_cred_names:
                msg = "Valid credential not found for target: %s" % sliver_name
                raise Forbidden(msg)
 
    ########################################
    ########## registry oriented
    ########################################

    ########## disabled users 
    def is_enabled(self, record):
        # all records are enabled
        return True

    def augment_records_with_testbed_info(self, sfa_records):
        return self.fill_record_info(sfa_records)

    def init_compute_manager_conn(self):
        from sfa.util.config import Config
        import sfa.openstack.client as os_client
        opts = os_client.parse_accrc(Config().SFA_NOVA_NOVARC)
        self.shell.compute_manager.connect( username=opts.get('OS_USERNAME'), \
                                            tenant=opts.get('OS_TENANT_NAME'),\
                                            password=opts.get('OS_PASSWORD') )
        logger.info( "Initialize Openstack connection from novarc file." )
    
    """ cwkim: it'll be removed.
    def find_user_info(self, user_name):
        users = self.api.dbsession().query(RegRecord).filter_by(type='user').all()
        # The users are in local DB
        for user in users:
            if user_name == user.os_user_nm:
                auth_name = user.os_auth_nm
                pwd = user.os_user_pw
                break
        # The users are related with federation
        else:
            auth_name = None
            pwd = user_name
        return auth_name, pwd

    def find_slice_info(self, slice_urn):
        slice_hrn = OSXrn(xrn=slice_urn, type='slice').get_hrn()
        slices = self.api.dbsession().query(RegRecord).filter_by(type='slice').all()
        # The slices are in local DB
        for slice in slices:
            if slice_hrn == slice.os_slice_nm:
                tenant_name = slice.os_slice_nm
                user_name = slice.os_user_nm
                break
        # The slices are related with federation
        else:
            tenant_name = slice_hrn
            xrn = Xrn(slice_urn)
            user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        return user_name, tenant_name
    """

    # Create the user or tenant depending on the type
    def register (self, sfa_record, hrn, pub_key):
        # Optimized for Openstack
        records = []
        if sfa_record['type'] == 'slice':
            slice, users = self.register_slice(sfa_record, hrn)
            slice_record = {'type':'slice', 'os_slice_id':slice.id, \
                            'os_slice_name':slice.name, 'os_user_name':users[0]}
            records.append(slice_record)
        elif sfa_record['type'] == 'user':
            user, auth_name = self.register_user(sfa_record, hrn, pub_key)
            user_record = {'type':'user', 'os_user_id':user.id, \
                           'os_user_name':user.name, 'os_user_pw':sfa_record.get('pwd'), \
                           'os_auth_name': auth_name}
            records.append(user_record)
        elif sfa_record['type'] == 'authority':
            authority = self.register_authority(sfa_record, hrn)
            authority_record = {'type':'authority', 'os_auth_id':authority.id, \
                                'os_auth_name':authority.name}
            records.append(authority_record)
        else:
            raise Exception(sfa_record['type'])
        return records

    def register_slice(self, sfa_record, hrn):
        aggregate = OSAggregate(self)
        
        # Get SFA client names
        users = []
        researchers = sfa_record.get('reg-researchers', [])
        pi = sfa_record.get('pi')
        if len(researchers):
            for researcher in researchers:
                name = OSXrn(xrn=researcher, type='user').get_hrn()
                users.append(name)
        elif pi:
            name = OSXrn(xrn=pi, type='user').get_hrn()
            users.append(name)
        else:
            logger.warnning("You should input options with researcher(s) or pi.")
        users = list(set(users))

        # Check if this is username-slicename or not
        if sfa_record.get('hrn').find('-') == -1:
            tenant_name = ( OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_authority_hrn() + '.' \
                            + OSXrn(xrn=users[0], type='user').get_leaf() + '-' \
                            + OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_leaf() )
        else:
            tenant_name = ( OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_authority_hrn() + '.' \
                            + OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_leaf() )

        tenant = aggregate.create_tenant(tenant_name, sfa_record.get('description', None))
   
        # the researcher(s) or pi is/are registered by keystone role.
        admin_role = self.shell.auth_manager.roles.find(name='admin')
        member_role = self.shell.auth_manager.roles.find(name='Member')
        if len(researchers):
            for researcher in researchers:
                researcher_name = OSXrn(xrn=researcher, type='user').get_hrn()
                user = self.shell.auth_manager.users.find(name=researcher_name)
                if self.shell.auth_manager.roles.roles_for_user(user, tenant).count(member_role) == 0:
                    self.shell.auth_manager.roles.add_user_role(user, member_role, tenant)
        elif pi:
            pi_name = OSXrn(xrn=pi, type='user').get_hrn()
            user = self.shell.auth_manager.users.find(name=pi_name)
            if self.shell.auth_manager.roles.roles_for_user(user, tenant).count(admin_role) == 0:
                self.shell.auth_manager.roles.add_user_role(user, admin_role, tenant)
        else:
            logger.warnning("You should input options with researcher(s) or pi.")
        return tenant, users
       
    def register_user(self, sfa_record, hrn, pub_key):
        aggregate = OSAggregate(self)
        # add person roles, projects and keys
        auth_hrn = Xrn(hrn).get_authority_hrn()
        auth_tenant_name = OSXrn(xrn=auth_hrn, type='authority').get_tenant_name()  
        auth_tenant = self.shell.auth_manager.tenants.find(name=auth_tenant_name)

        user = aggregate.create_user(user_name=sfa_record.get('hrn'), password=sfa_record.get('pwd'), \
                         tenant_id=auth_tenant.id, email=sfa_record.get('email', None), enabled=True)
        
        keys = sfa_record.get('keys', [])
        for key in keys:
            keyname = OSXrn(xrn=hrn, type='user').get_slicename()
            #KOREN: Update connection for the current client
            self.shell.compute_manager.connect(username=user.name, tenant=auth_tenant.name, \
                                               password=sfa_record.get('pwd')) 
            self.shell.compute_manager.keypairs.create(name=keyname, public_key=key)
        #KOREN: Reset the connection of admin
        self.init_compute_manager_conn()
        return user, auth_tenant.name

    def register_authority(self, sfa_record, hrn):
        aggregate = OSAggregate(self)
        auth_name = OSXrn(xrn=hrn, type='authority').get_tenant_name()
        tenant = aggregate.create_tenant(tenant_name=auth_name, \
                                         description=sfa_record.get('description', None))
        return tenant

    # For Federation
    def register_federation(self, user_hrn, slice_hrn, keys, email=None):
        aggregate = OSAggregate(self)

        # Create a slice of the federation user
        tenant = aggregate.create_tenant(tenant_name=slice_hrn, description=user_hrn)

        # Create a user of the federation user
        # This password is the same as the user hrn.
        user = aggregate.create_user(user_name=user_hrn,  password=user_hrn, \
                                     tenant_id=tenant.id, email=email, enabled=True)

        member_role = self.shell.auth_manager.roles.find(name='Member')
        # Check if the user has roles or not
        if self.shell.auth_manager.roles.roles_for_user(user, tenant).count(member_role) == 0:
            self.shell.auth_manager.roles.add_user_role(user, member_role, tenant)

        # Check if keys exist or not
        if keys is not None: 
            # Check if the user has keys or not
            if len(keys) < 1:
                key = None
            else:
                key = keys[0]
            keyname = OSXrn(xrn=user_hrn, type='user').get_slicename()
            #KOREN: Update connection for the current client
            self.shell.compute_manager.connect(username=user.name, tenant=tenant.name, password=user_hrn)
            keypair_list = self.shell.compute_manager.keypairs.list()
            for keypair in keypair_list:
                if keyname == keypair.name:
                    break
            else:
                self.shell.compute_manager.keypairs.create(name=keyname, public_key=key)
            #KOREN: Reset the connection of admin
            self.init_compute_manager_conn()
        logger.info( "The federation user[%s] has the slice[%s] as member role." % \
                     (user.name, tenant.name) )
        return user, tenant

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
                project_manager = Xrn(pis[0], 'user').get_hrn()
            elif researchers:
                project_manager = Xrn(researchers[0], 'user').get_hrn()
            self.shell.auth_manager.modify_project(name, project_manager, description)

        elif type == "user":
            #KOREN TODO - check if user is or not.
            # can techinally update access_key and secret_key,
            # but that is not in our scope, so we do nothing.  
            pass
        return True
        
    ##########
    def remove(self, sfa_record):
        type=sfa_record['type']
        
        if type == 'user':
            keyname = OSXrn(xrn=sfa_record.get('hrn'), type='user').get_slicename()
            user = self.shell.auth_manager.users.find(name=sfa_record.get('hrn'))
            if user:
                self.shell.auth_manager.users.delete(user.id)
                #KOREN: Update connection for the current client
                auth_name, pwd = self.find_user_info(user_name=user.name)
#                local_users = self.api.dbsession().query(RegRecord).filter_by(type='user').all()
#                for local_user in local_users:
#                    if user.name == local_user.os_user_nm:
#                        auth_name = local_user.os_auth_nm
#                        pwd = local_user.os_user_pw
                self.shell.compute_manager.connect(username=user.name, tenant=auth_name, password=pwd)
                self.shell.compute_manager.keypairs.delete(key=keyname)
                #KOREN: Reset the connection of admin
                self.init_compute_manager_conn()
            logger.info("User[%s] removed from Openstack and SFA registry" % user.name)

        elif type == 'slice':
            slice = self.shell.auth_manager.tenants.find(name=sfa_record.get('hrn'))
            if slice:
                self.shell.auth_manager.tenants.delete(slice.id)
            logger.info("Slice[%s] removed from Openstack and SFA registry" % slice.name)

        elif type == 'authority':
            auth = self.shell.auth_manager.tenants.find(name=sfa_record['hrn'])
            if auth:
                self.shell.auth_manager.tenants.delete(auth.id)
            logger.info("Authority[%s] removed from Openstack and SFA registry" % auth.name)
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
        return records

    def fill_user_record_info(self, record):
        xrn = Xrn(record['hrn'])
        name = xrn.get_leaf()
        record['name'] = name
        user = self.shell.auth_manager.users.find(name=name)
        record['email'] = user.email
        tenant = self.shell.auth_manager.tenants.find(name=user.name)
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
        keys = self.shell.compute_manager.keypairs.findall(name=record['hrn'])
        record['keys'] = [key.public_key for key in keys]
        return record

    def fill_slice_record_info(self, record):
        tenant_name = hrn_to_os_tenant_name(record['hrn'])
        tenant = self.shell.auth_manager.tenants.find(name=tenant_name)
        auth_tenant_name = OSXrn(xrn=tenant_name).get_authority_hrn()
        auth_tenant = self.shell.auth_manager.tenants.find(name=auth_tenant_name)
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
        for user in auth_tenant.list_users():
            for role in self.shell.auth_manager.roles.roles_for_user(user, auth_tenant):
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
        elif subject_type =='authority' and target_type == 'user':
            logger.info('affiliated relation to maintain, %s -> %s'%(subject_type,target_type))
        else:
            logger.info('unexpected relation to maintain, %s -> %s'%(subject_type,target_type))

        
    ########################################
    ########## aggregate oriented
    ########################################

    def testbed_name (self): return "openstack"

    def aggregate_version (self):
        return {}

    # first 2 args are None in case of resource discovery
    def list_resources (self, version=None, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
        rspec = aggregate.list_resources(version=version, options=options)
        return rspec

    def describe(self, urns, version=None, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
        return aggregate.describe(urns, version=version, options=options)
    
    def status (self, urns, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
        desc =  aggregate.describe(urns)
        status = {'geni_urn': desc['geni_urn'],
                  'geni_slivers': desc['geni_slivers']}
        return status

    def allocate (self, urn, rspec_string, expiration, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
        rspec = RSpec(rspec_string)
        xrn = Xrn(urn)
        slice_hrn = xrn.get_hrn()
        tenant_name = OSXrn(xrn=slice_hrn, type='slice').get_hrn()
        instance_name = hrn_to_os_slicename(slice_hrn)
        tenants = self.shell.auth_manager.tenants.findall()

        # collect public keys & get the user name
        users = options.get('geni_users', [])
        pubkeys = []
        key_name = None

        if len(users) >= 1:
            for user in users:
                #TODO: We currently support one user name.
                user_name = Xrn(user.get('urn')).get_hrn()
                pubkeys.extend(user['keys'])
            for tenant in tenants:
                # Check if the tenant of the user exists in local OS or not
                if tenant_name == tenant.name:
                    try:
                        self.shell.auth_manager.users.find(name=user_name)
                    except:
                        user, tenant = self.register_federation(user_hrn=user_name, \
                                            slice_hrn=tenant_name, keys=pubkeys, email=None)
                    break
            else:
                user, tenant = self.register_federation(user_hrn=user_name, \
                                                        slice_hrn=tenant_name, keys=None, email=None)
            #KOREN: Update connection for the current client
            auth_name, pwd = self.find_user_info(user_name=user_name)
#            local_users = self.api.dbsession().query(RegRecord).filter_by(type='user').all()
#            for local_user in local_users:
#                if user_name == local_user.os_user_nm:
#                    pwd = local_user.os_user_pw
#                    break
#            else:
#                pwd = user_name
            self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
            keypair_list = self.shell.compute_manager.keypairs.list()
            keyname = OSXrn(xrn=user_name, type='user').get_slicename()
            for keypair in keypair_list:
                if keyname == keypair.name:
                    key_name = keypair.name
                    break
            else:
                raise SfaNotImplemented("No handle!")
            #KOREN: Reset the connection of admin
            self.init_compute_manager_conn()
#            key_name = aggregate.create_instance_key(slice_hrn, users[0])

        # In case of federation or non-options
        elif len(users) < 1:
            if options.get('actual_caller_hrn') is None:
                user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
            else:
                user_name = options.get('actual_caller_hrn')
            for tenant in tenants:
                # Check if the tenant of the user in local OS or not
                if tenant_name == tenant.name:
                    try:
                        self.shell.auth_manager.users.find(name=user_name)
                    except:
                        user, tenant = self.register_federation(user_hrn=user_name, \
                                                                slice_hrn=tenant_name, keys=pubkeys, email=None)
                    break
            else:
                user, tenant = self.register_federation(user_hrn=user_name, \
                                                        slice_hrn=tenant_name, keys=None, email=None)
             #TODO: Wrapper for federation needs at least one pubkey of the user extracted by 'options'!!
#            name = OSXrn(xrn=user_name, type='user').get_slicename()
#            key_name = self.shell.compute_manager.keypairs.get(name).name

        else:
            raise SfaNotImplemented("No handle!")
        
        slivers = aggregate.run_instances(instance_name, tenant_name, user_name, \
                                          rspec_string, expiration, key_name, pubkeys)
        return aggregate.describe(urns=[urn], version=rspec.version)
    
    def provision(self, urns, options=None):
        if options is None: options={} 
        aggregate = OSAggregate(self)

        # Connected with the requested user
        user_name, tenant_name = self.find_slice_info(slice_urn=urns[0])
#        slice_hrn = OSXrn(xrn=urns[0], type='slice').get_hrn()
#        local_slices = self.api.dbsession().query(RegRecord).filter_by(type='slice').all()
#        for slice in local_slices:
#            if slice_hrn == slice.os_slice_nm:
#                tenant_name = slice.os_slice_nm
#                user_name = slice.os_user_nm
#                break
#        else:
#            xrn = Xrn(urns[0]) 
#            tenant_name = slice_hrn
#            user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        auth_name, pwd = self.find_user_info(user_name=user_name)
#        local_users = self.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)

        instances = aggregate.get_instances(urns)
        # Allocate new floating IP per the instance
        servers = aggregate.check_floatingip(instances, True)
        aggregate.create_floatingip(tenant_name, servers)

        # Update sliver allocation states and set them to geni_provisioned
        sliver_ids = [instance.id for instance in instances]
        dbsession=self.api.dbsession()
        SliverAllocation.set_allocations(sliver_ids, 'geni_provisioned', dbsession)
        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options['geni_rspec_version'])
        return self.describe(urns, rspec_version, options=options) 

    def delete(self, urns, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
      
        # Connected with the requested user
        user_name, tenant_name = self.find_slice_info(slice_urn=urns[0])
#        slice_hrn = OSXrn(xrn=urns[0], type='slice').get_hrn()
#        local_slices = self.api.dbsession().query(RegRecord).filter_by(type='slice').all()
#        for slice in local_slices:
#            if slice_hrn == slice.os_slice_nm:
#                tenant_name = slice.os_slice_nm
#                user_name = slice.os_user_nm
#                break
#        else:
#            xrn = Xrn(urns[0]) 
#            tenant_name = slice_hrn
#            user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        auth_name, pwd = self.find_user_info(user_name=user_name)
#        local_users = self.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
      
        # collect sliver ids so we can update sliver allocation states after
        # we remove the slivers.
        instances = aggregate.get_instances(urns)
        # Release the floating IPs of instances
        servers = aggregate.check_floatingip(instances, False)
        aggregate.delete_floatingip(servers)

        sliver_ids = []
        id_set = set()
        for instance in instances:
            sliver_hrn = "%s.%s" % (self.hrn, instance.id)
            sliver_ids.append(Xrn(sliver_hrn, type='sliver').urn)
            # delete the instance related with requested tenant
            aggregate.delete_instance(instance)
            id_set.add(instance.tenant_id)
        
        tenant_ids = list(id_set)
        for tenant_id in tenant_ids:
            # delete both the router(s) and interfaces related with requested tenant
            aggregate.delete_router(tenant_id=tenant_id)
            # delete both the network and subnet related with requested tenant
            aggregate.delete_network(tenant_id=tenant_id)
            
        # delete sliver allocation states
        dbsession=self.api.dbsession()
        SliverAllocation.delete_allocations(sliver_ids, dbsession)

        # return geni_slivers
        geni_slivers = []
        for sliver_id in sliver_ids:
            geni_slivers.append(
                 {'geni_sliver_urn': sliver_id,
                  'geni_allocation_status': 'geni_unallocated',
                  'geni_expires': datetime_to_string(utcparse(time.time()))})
#                 'geni_expires': None})        
        return geni_slivers

    def renew (self, urns, expiration_time, options=None):
        if options is None: options={}
        description = self.describe(urns, None, options)
        return description['geni_slivers']

    def perform_operational_action  (self, urns, action, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
        action = action.lower() 
        if action == 'geni_start':
            action_method = aggregate.start_instances
        elif action == 'geni_stop':
            action_method = aggregate.stop_instances
        elif action == 'geni_restart':
            action_method = aggreate.restart_instances
        else:
            raise UnsupportedOperation(action)

         # fault if sliver is not full allocated (operational status is geni_pending_allocation)
        description = self.describe(urns, None, options)
        for sliver in description['geni_slivers']:
            if sliver['geni_operational_status'] == 'geni_pending_allocation':
                raise UnsupportedOperation(action, "Sliver must be fully allocated (operational status is not geni_pending_allocation)")
        #
        # Perform Operational Action Here
        #

        instances = aggregate.get_instances(urns) 
        for instance in instances:
            tenant_name = self.shell.auth_manager.client.tenant_name
            action_method(tenant_name, instance.name, instance.id)
        description = self.describe(urns)
        geni_slivers = self.describe(urns, None, options)['geni_slivers']
        return geni_slivers

    def shutdown(self, xrn, options=None):
        if options is None: options={}
        # Update Openstack connection for client
        user_name, tenant_name = self.find_slice_info(slice_urn=xrn)
#        slice_hrn = OSXrn(xrn=xrn, type='slice').get_hrn()
#        local_slices = self.api.dbsession().query(RegRecord).filter_by(type='slice').all()
#        for slice in local_slices:
#            if slice_hrn == slice.os_slice_nm:
#                tenant_name = slice.os_slice_nm
#                user_name = slice.os_user_nm
#                break
#        else:
#            tenant_name = slice_hrn
#            user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        auth_name, pwd = self.find_user_info(user_name=user_name)
#        local_users = self.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
        instances = self.shell.compute_manager.servers.findall(name=OSXrn(xrn=xrn, type='slice').get_slicename())
        for instance in instances:
            self.shell.compute_manager.servers.stop(instance.id)
        return True
