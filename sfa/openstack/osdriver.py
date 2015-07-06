######################################################################################################
# Edited on Jun 20, 2015                                                                             #
# Code modified by Chaima Ghribi.                                                                    #
# The original code is available on github at https://github.com/onelab-eu/sfa/tree/openstack-driver.#
# Modifications are noted as comments in the code itself.                                            #
# @contact: chaima.ghribi@it-sudparis.eu                                                             #
# @organization: Institut Mines-Telecom - Telecom SudParis                                           #
######################################################################################################

import time
import datetime

from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
     RecordNotFound, SfaNotImplemented, SfaInvalidArgument, UnsupportedOperation

from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf, get_authority
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename, hrn_to_os_tenant_name
from sfa.util.cache import Cache
from sfa.trust.credential import Credential
# used to be used in get_ticket
#from sfa.trust.sfaticket import SfaTicket
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec
from sfa.storage.model import SliverAllocation

# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver
from sfa.openstack.shell import Shell
from sfa.openstack.osaggregate import OSAggregate
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename, hrn_to_os_tenant_name

# for exception
from keystoneclient import exceptions as KeystoneExceptions
from novaclient import exceptions as NovaExceptions

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict( [ (rec[key],rec) for rec in recs ] )


class OpenstackDriver(Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, api):
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
    def is_enabled (self, record):
        # all records are enabled
        return True

    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)

    def init_compute_manager_conn(self):
        from sfa.util.config import Config 
        import sfa.openstack.client as os_client
        opts = os_client.parse_accrc(Config().SFA_NOVA_NOVARC)
        self.shell.compute_manager.connect( username=opts.get('OS_USERNAME'),  \
                                            tenant=opts.get('OS_TENANT_NAME'), \
                                            password=opts.get('OS_PASSWORD')   )
        logger.info( "Initialize Openstack connection from novarc file." )

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        
        if sfa_record['type'] == 'slice':
            record = self.register_slice(sfa_record, hrn)         
        elif sfa_record['type'] == 'user':
            record = self.register_user(sfa_record, hrn, pub_key)
        elif sfa_record['type'] == 'authority': 
            record = self.register_authority(sfa_record, hrn)
        else:
            raise Exception(sfa_record['type'])
        # We should be returning the records id as a pointer but
        # this is a string and the records table expects this to be an int.
        #return record.id
        return -1

    def register_slice(self, sfa_record, hrn):
        aggregate = OSAggregate(self)

        # Get the user names (SFA client names)
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
        # TODO: for now, we just support 1 user to make tenant
        if sfa_record.get('hrn').find('-') == -1:
            tenant_name = ( OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_authority_hrn() + '.' \
                            + OSXrn(xrn=users[0], type='user').get_leaf() + '-'                      \
                            + OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_leaf()              ) 
        else:
            tenant_name = ( OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_authority_hrn() + '.' \
                            + OSXrn(xrn=sfa_record.get('hrn'), type='slice').get_leaf()              )
        description = sfa_record.get('description', None)
        tenant = aggregate.create_tenant(tenant_name, description)

        # Add suitable roles to the user
        admin_role = self.shell.auth_manager.roles.find(name='admin')
        member_role = self.shell.auth_manager.roles.find(name='_member_')
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
        return tenant
           
    def register_user(self, sfa_record, hrn, pub_key):
        aggregate = OSAggregate(self)

        # Get the authority tenant info for initialization of a user
        auth_hrn = Xrn(hrn).get_authority_hrn()
        auth_tenant_name = OSXrn(xrn=auth_hrn, type='authority').get_tenant_name() 
        auth_tenant = self.shell.auth_manager.tenants.find(name=auth_tenant_name)

        # Create a user based on the auth tenant
        user_name = sfa_record.get('hrn')
        email = sfa_record.get('email', None)
        user = aggregate.create_user(user_name=user_name, password=user_name, \
                                     tenant_id=auth_tenant.id, email=email, enabled=True) 

        keys = sfa_record.get('keys', [])
        for key in keys:
            keyname = OSXrn(xrn=hrn, type='user').get_slicename()
            # Update connection for the current user
            self.shell.compute_manager.connect(username=user.name, tenant=auth_tenant.name, \
                                               password=user.name)
            self.shell.compute_manager.keypairs.create(name=keyname, public_key=key)

        # Update initial connection info
        self.init_compute_manager_conn()
        return user

    def register_authority(self, sfa_record, hrn):
        aggregate = OSAggregate(self)
        auth_name = OSXrn(xrn=hrn, type='authority').get_tenant_name()
        description = sfa_record.get('description', None)
        # Create a authority tenant
        auth_tenant = aggregate.create_tenant(tenant_name=auth_name, description=description)
        return auth_tenant
        
    def register_federation(self, user_hrn, slice_hrn, keys, email=None):
        aggregate = OSAggregate(self)

        # Create a slice of the federation user
        tenant = aggregate.create_tenant(tenant_name=slice_hrn, description=user_hrn)
        # Create a user of the federation user
        user = aggregate.create_user(user_name=user_hrn,  password=user_hrn, \
                                     tenant_id=tenant.id, email=email, enabled=True)

        # Check if the user has roles or not 

        # Code modified by Chaima Ghribi
        member_role = self.shell.auth_manager.roles.find(name='_member_')
        ###

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
            # Update connection for the current client 
            self.shell.compute_manager.connect(username=user.name, tenant=tenant.name, password=user_hrn)
            keypair_list = self.shell.compute_manager.keypairs.list()
            for keypair in keypair_list:
                if keyname == keypair.name:
                    break
            else:
                self.shell.compute_manager.keypairs.create(name=keyname, public_key=key)

            # Update initial connection info
            self.init_compute_manager_conn()
            logger.info( "The federation user[%s] has the slice[%s] as member role." % \
                         (user.name, tenant.name)                                      ) 
            return user

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
            # TODO: check if user is or not.
            # can techinally update access_key and secret_key,
            # but that is not in our scope, so we do nothing.  
            pass
        return True
        

    ##########
    def remove (self, sfa_record):
        type = sfa_record['type']

        if type == 'user':
            user=None
            hrn = sfa_record.get('hrn')
            try:
                user = self.shell.auth_manager.users.find(name=hrn)
                keyname = OSXrn(xrn=hrn, type='user').get_slicename()
            except(KeystoneExceptions.NotFound):
                print "This user[%s] isn't exist in Openstack" % hrn
                logger.warn("The user[%s] isn't exist in Openstack" % hrn)
            if user:
                self.shell.auth_manager.users.delete(user.id)
                # Update connection for the current client
                auth_name = Xrn(hrn).get_authority_hrn()
                self.shell.compute_manager.connect(username=user.name, tenant=auth_name, password=user.name)
                self.shell.compute_manager.keypairs.delete(key=keyname)
                # Update initial connection info
                self.init_compute_manager_conn()
                logger.info("User[%s] removed from Openstack and SFA registry" % user.name) 
        
        elif type == 'slice':
            hrn = sfa_record.get('hrn')
            slice = self.shell.auth_manager.tenants.find(name=hrn)
            if slice:
                self.shell.auth_manager.tenants.delete(slice.id)
            logger.info("Slice[%s] removed from Openstack and SFA registry" % slice.name) 
        
        elif type == 'authority':   
            hrn = sfa_record.get('hrn')
            auth_tenant = self.shell.auth_manager.tenants.find(name=hrn)
            if auth_tenant:
                self.shell.auth_manager.tenants.delete(auth_tenant.id) 
            logger.info("Authority[%s] removed from Openstack and SFA registry" % auth_tenant.name)

        else:
            raise Exception(type)
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
            elif record['type'] == 'authority':
                record = self.fill_auth_record_info(record)
            else:
                continue
            record['geni_urn'] = hrn_to_urn(record['hrn'], record['type'])
            record['geni_certificate'] = record['gid'] 
        return records

    def fill_user_record_info(self, record):
        name = record.get('hrn')
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

    def update_relation (self, subject_type, target_type, relation_name, subject_id, target_ids):
        if subject_type =='slice' and target_type == 'user':
            logger.info('affiliated relation to maintain, %s -> %s' % (subject_type,target_type))
        elif subject_type =='authority' and target_type == 'user':
            logger.info('affiliated relation to maintain, %s -> %s' % (subject_type,target_type))
        else:
            logger.info('unexpected relation to maintain, %s -> %s' % (subject_type,target_type))

        
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
        rspec =  aggregate.list_resources(version=version, options=options)
        return rspec

    def describe(self, urns, version=None, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
        return aggregate.describe(urns, version=version, options=options)
    
    def status (self, urns, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)
  
        # TODO: Change to more dynamic
        version_manager = VersionManager()
        version_dict = {'type':'KOREN', 'version':'1', 'content_type':'manifest'}
        version = version_manager.get_version(version_dict)
        desc = aggregate.describe(urns, version=version, options=options)
        status = {'geni_urn': desc['geni_urn'],
                  'geni_slivers': desc['geni_slivers']}
        return status

    def secgroups_with_rules(self, rspec_groups):
        sec_groups=[]
        for rspec_group in rspec_groups:
            rspec_group_name = rspec_group.get('name')
            try:
                # Check if the security group exists
                group = self.shell.compute_manager.security_groups.find(name=rspec_group_name)
                # Check if the security rules of the group exist 
                rspec_rules = rspec_group.get('rules')
                if rspec_rules:
                    ori_rules = group.rules
                    for rspec_rule in rspec_rules:
                        for ori_rule in ori_rules:
                            if (rspec_rule.get('ip_protocol') == str(ori_rule.get('ip_protocol'))) and \
                               (rspec_rule.get('from_port') == str(ori_rule.get('from_port'))) and \
                               (rspec_rule.get('to_port') == str(ori_rule.get('to_port'))) and \
                               (rspec_rule.get('ip_range') == str(ori_rule.get('ip_range'))):
                                break
                        else:
                            # New security rules of the group
                            parent_group_id = group.id
                            if rspec_rule.get('ip_protocol').lower() is 'none':
                                logger.error("ip_protocol should be one of 'tcp', 'udp' or 'icmp'")
                                break
                            else:
                                ip_protocol = rspec_rule.get('ip_protocol')
                            if rspec_rule.get('from_port').lower() is 'none':
                                from_port = 0
                            elif rspec_rule.get('from_port').lower() is 'any':
                                from_port = -1
                            else:
                                from_port = int(rspec_rule.get('from_port'))
                            if rspec_rule.get('to_port').lower() is 'none':
                                to_port = 0
                            elif rspec_rule.get('to_port').lower() is 'any':
                                to_port = -1
                            else:    
                                to_port = int(rspec_rule.get('to_port'))
                            if (rspec_rule.get('ip_range') is '{}') or (rspec_rule.get('ip_range') is 'none'):
                                cidr = None
                            else:
                                cidr = rspec_rule.get('ip_range')
                            self.shell.compute_manager.security_group_rules.create(parent_group_id, \
                                                                            ip_protocol, from_port, to_port, cidr)
                    group = self.shell.compute_manager.security_groups.find(id=group.id)
                    sec_groups.append(group)
                else:
                    sec_groups.append(group)
                        
            except(NovaExceptions.NotFound):
                # New security group
                description = rspec_group.get('description')
                if not description:
                    description = None
                group = self.shell.compute_manager.security_groups.create(name=rspec_group_name, description=description)
                # New security rules of the group
                rspec_rules = rspec_group.get('rules')
                for rspec_rule in rspec_rules:
                    parent_group_id = group.id
                    if rspec_rule.get('ip_protocol').lower() is 'none':
                        logger.error("ip_protocol should be one of 'tcp', 'udp' or 'icmp'")
                        break
                    else:
                        ip_protocol = rspec_rule.get('ip_protocol')
                    if rspec_rule.get('from_port').lower() is 'none':
                        from_port = 0
                    elif rspec_rule.get('from_port').lower() is 'any':
                        from_port = -1
                    else:
                        from_port = int(rspec_rule.get('from_port'))
                    if rspec_rule.get('to_port').lower() is 'none':
                        to_port = 0
                    elif rspec_rule.get('to_port').lower() is 'any':
                        to_port = -1
                    else: 
                        to_port = int(rspec_rule.get('to_port'))
                    if (rspec_rule.get('ip_range') is '{}') or (rspec_rule.get('ip_range') is 'none'):
                        cidr = None
                    else:
                        cidr = rspec_rule.get('ip_range')
                    self.shell.compute_manager.security_group_rules.create(parent_group_id, \
                                                                    ip_protocol, from_port, to_port, cidr)
                group = self.shell.compute_manager.security_groups.find(id=group.id)
                sec_groups.append(group)
                continue
        return sec_groups

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
                # TODO: We currently support one user name.
                user_name = Xrn(user.get('urn')).get_hrn()
                pubkeys.extend(user['keys'])
            for tenant in tenants:
                # Check if the tenant of the user exists in local OS or not
                if tenant_name == tenant.name:
                    try:
                        self.shell.auth_manager.users.find(name=user_name)
                    except:
                        user = self.register_federation(user_hrn=user_name, \
                                    slice_hrn=tenant_name, keys=pubkeys, email=None)
                    break
            else:
                # Code modified by Chaima Ghribi
                user = self.register_federation(user_hrn=user_name, \
                            slice_hrn=tenant_name, keys=pubkeys, email=None)
                ###
  
            # Update connection for the current client
            self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)
            keypair_list = self.shell.compute_manager.keypairs.list()
            keyname = OSXrn(xrn=user_name, type='user').get_slicename()
            for keypair in keypair_list:
                if keyname == keypair.name:
                    key_name = keypair.name
                    break
            else:
                raise SfaNotImplemented("No handle!")
            
            # Update initial connection info
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
                        user = self.register_federation(user_hrn=user_name, \
                                    slice_hrn=tenant_name, keys=pubkeys, email=None)
                    break
            else:
                user = self.register_federation(user_hrn=user_name, \
                            slice_hrn=tenant_name, keys=None, email=None)
            # TODO: Wrapper for federation needs at least one pubkey of the user extracted by 'options'!!
#            name = OSXrn(xrn=user_name, type='user').get_slicename()
#            key_name = self.shell.compute_manager.keypairs.get(name).name

        else:
            raise SfaNotImplemented("No handle!")

        slivers = aggregate.run_instances(tenant_name, user_name, rspec_string, key_name, pubkeys)
        # Update sliver allocations
        for sliver in slivers:
            component_id = sliver.metadata.get('component_id')
            sliver_id = OSXrn(name=('koren'+'.'+ sliver.name), id=sliver.id, type='node+openstack').get_urn()
            record = SliverAllocation( sliver_id=sliver_id,
                                       component_id=component_id,
                                       allocation_state='geni_allocated')
            record.sync(self.api.dbsession())
        return aggregate.describe(urns=[urn], version=rspec.version)

    def provision(self, urns, options=None):
        if options is None: options={}
        # update sliver allocation states and set them to geni_provisioned
        aggregate = OSAggregate(self)

        # Update connection for the current client
        xrn = Xrn(urns[0], type='slice')
        tenant_name = OSXrn(xrn=urns[0], type='slice').get_hrn() 

        # Code modified by Chaima Ghribi
        tenant_info = self.shell.auth_manager.tenants.find(name=tenant_name)
        user_name = tenant_info.description
        ###

        self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)
        
        instances = aggregate.get_instances(xrn)
        # Allocate new floating IP per the instance
        servers = aggregate.check_floatingip(instances, True)
        aggregate.create_floatingip(tenant_name, servers)

        sliver_ids=[]
        for instance in instances:
            sliver_id = OSXrn(name=('koren'+'.'+ instance.name), id=instance.id, type='node+openstack').get_urn()
            sliver_ids.append(sliver_id)
        dbsession=self.api.dbsession()
        SliverAllocation.set_allocations(sliver_ids, 'geni_provisioned', dbsession)
        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options['geni_rspec_version'])
        return self.describe(urns, rspec_version, options=options)

    def delete(self, urns, options=None):
        if options is None: options={}
        aggregate = OSAggregate(self)

        # Update connection for the current client
        xrn = Xrn(urns[0], type='slice')
        tenant_name = OSXrn(xrn=urns[0], type='slice').get_hrn()

        # Code modified by Chaima Ghribi
        tenant_info = self.shell.auth_manager.tenants.find(name=tenant_name)
        user_name = tenant_info.description
        ###

        self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)

        # collect sliver ids so we can update sliver allocation states after
        # we remove the slivers.
        instances = aggregate.get_instances(xrn)
        # Release the floating IPs of instances
        servers = aggregate.check_floatingip(instances, False)
        aggregate.delete_floatingip(servers)

        sliver_ids = []
        id_set = set()
        for instance in instances:
            sliver_id = OSXrn(name=('koren'+'.'+ instance.name), id=instance.id, type='node+openstack').get_urn()
            sliver_ids.append(sliver_id)
            # delete the instance related with requested tenant
            aggregate.delete_instance(instance)
            id_set.add(instance.tenant_id)       

        tenant_ids = list(id_set)
        for tenant_id in tenant_ids:
            # Delete both the router(s) and interfaces related with requested tenant
            aggregate.delete_router(tenant_id=tenant_id)
            # Delete both the network and subnet related with requested tenant
            aggregate.delete_network(tenant_id=tenant_id)

        # Delete sliver allocation states
        dbsession=self.api.dbsession()
        SliverAllocation.delete_allocations(sliver_ids, dbsession)

        # Return geni_slivers
        geni_slivers = []
        for sliver_id in sliver_ids:
            geni_slivers.append(
                { 'geni_sliver_urn': sliver_id,
                  'geni_allocation_status': 'geni_unallocated',
#                  'geni_expires': datetime_to_string(utcparse(time.time())) })
                  'geni_expires': None })
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
                raise UnsupportedOperation(action, \
                      "Sliver must be fully allocated (operational status is not geni_pending_allocation)")

        #
        # Perform Operational Action Here
        #
    
        xrn = Xrn(urns[0], type='slice')
        instances = aggregate.get_instances(xrn) 
        for instance in instances:
            tenant_name = self.shell.auth_manager.client.tenant_name
            action_method(tenant_name, instance.name, instance.id)
        description = self.describe(urns)
        geni_slivers = self.describe(urns, None, options)['geni_slivers']
        return geni_slivers

    def shutdown(self, urn, options=None):
        if options is None: options={}

        # Update connection for the current client
        xrn = Xrn(urn)
        osxrn = OSXrn(xrn=urn, type='slice')

        # Code modified by Chaima Ghribi
        tenant_name = osxrn.get_hrn()
        tenant_info = self.shell.auth_manager.tenants.find(name=tenant_name)
        user_name = tenant_info.description
        ###

        self.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)

        # Code modified by Chaima Ghribi
        aggregate = OSAggregate(self)
        instances = aggregate.get_instances(xrn)
        for instance in instances:
            self.shell.compute_manager.servers.delete(instance.id)
        return True
        ###
