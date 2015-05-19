import os
import socket
import base64
import string
import random
import time    
from collections import defaultdict
from sfa.util.faults import SliverDoesNotExist
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import NodeElement
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.os_glance import DiskImage
from sfa.rspecs.elements.services import ServicesElement
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.fw_rule import FWRule
from sfa.util.xrn import Xrn, get_leaf, hrn_to_urn
from sfa.planetlab.plxrn import PlXrn 
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename
from sfa.rspecs.version_manager import VersionManager
from sfa.openstack.security_group import SecurityGroup
from sfa.client.multiclient import MultiClient
from sfa.util.sfalogging import logger
from sfa.storage.model import RegRecord, SliverAllocation

def pubkeys_to_user_data(pubkeys):
    user_data = "#!/bin/bash\n\n"
    for pubkey in pubkeys:
        pubkey = pubkey.replace('\n', '')
        user_data += "echo %s >> /root/.ssh/authorized_keys" % pubkey
        user_data += "\n"
        user_data += "echo >> /root/.ssh/authorized_keys"
        user_data += "\n"
    return user_data

def os_image_to_rspec_disk_image(image):
    img = DiskImage()
    img['name'] = image.name
    img['minDisk'] = image.minDisk
    img['minRam'] = image.minRam
    img['imgSize'] = image._info['OS-EXT-IMG-SIZE:size']
    img['status'] = image.status   
    return img

class OSAggregate:

    def __init__(self, driver):
        self.driver = driver

    def get_availability_zones(self, zones=None):
        #KOREN: Reset the connection of admin
        self.driver.init_compute_manager_conn()
#        import sfa.openstack.client as os_client
#        from sfa.util.config import Config as os_config
#        os_opts = os_client.parse_accrc(os_config().SFA_NOVA_NOVARC)
#        self.driver.shell.compute_manager.connect( username=os_opts.get('OS_USERNAME'), \
#                                                   tenant=os_opts.get('OS_TENANT_NAME'),\
#                                                   password=os_opts.get('OS_PASSWORD') )
        zone_list = []
        if not zones:
            availability_zones = self.driver.shell.compute_manager.availability_zones.list()
            for zone in availability_zones:
                if (zone.zoneState.get('available') == True) and \
                                                    (zone.zoneName != 'internal'):
                    zone_list.append(zone.zoneName)    
#            zones = ['nova']
        else:
            availability_zones = self.driver.shell.compute_manager.availability_zones.list()
            for a_zone in availability_zones:
                for i_zone in zones:
                    if a_zone.zoneName == i_zone:
                        if (a_zone.zoneState.get('available') == True) and \
                                                              (a_zone.zoneName != 'internal'):
                            zone_list.append(a_zone.zoneName)
        return zone_list
#            zones = [zone.name for zone in zones]
#        return zones

    def list_resources(self, version=None, options=None):
        if options is None: options={}
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        rspec = RSpec(version=version, user_options=options)
        nodes = self.get_aggregate_nodes()
        rspec.version.add_nodes(nodes)
        return rspec.toxml()

    def describe(self, urns, version=None, options=None):
        if options is None: options={}
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)        

        # Update OpenStack connection info.
        user_name, tenant_name = self.driver.find_slice_info(slice_urn=urns[0])
#        slice_hrn = OSXrn(xrn=urns[0], type='slice').get_hrn()
#        local_slices = self.driver.api.dbsession().query(RegRecord).filter_by(type='slice').all()
#        for slice in local_slices:
#            if slice_hrn == slice.os_slice_nm:
#                tenant_name = slice.os_slice_nm
#                user_name = slice.os_user_nm
#                break
#        else:
#            xrn = Xrn(urns[0])
#            tenant_name = slice_hrn
#            user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        auth_name, pwd = self.driver.find_user_info(user_name=user_name)
#        local_users = self.driver.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
#        tenant_name = OSXrn(xrn=urns[0], type='slice').get_tenant_name()
#        self.driver.shell.compute_manager.connect(username=Xrn(tenant_name).get_leaf(),tenant=tenant_name)
        # For delay to collect instance info
        time.sleep(3)
        # get instances from internal database
        instances = self.get_instances(urns)
        # lookup the sliver allocations using instances
        sliver_ids = [instance.id for instance in instances]
        constraint = SliverAllocation.sliver_id.in_(sliver_ids)
        sliver_allocations = self.driver.api.dbsession().query(SliverAllocation).filter(constraint)
        sliver_allocation_dict = {}
        for sliver_allocation in sliver_allocations:
            sliver_allocation_dict[sliver_allocation.sliver_id] = sliver_allocation
        
        geni_slivers = []
        rspec.xml.set('expires',  datetime_to_string(utcparse(time.time())))

        # add slivers
        rspec_nodes = []
        for instance in instances:
            rspec_nodes.append(self.instance_to_rspec_node(instance))
            geni_sliver = self.instance_to_geni_sliver(instance, sliver_allocation_dict)
            geni_slivers.append(geni_sliver)
        rspec.version.add_nodes(rspec_nodes)

        result = {'geni_urn': Xrn(urns[0]).get_urn(),
                  'geni_rspec': rspec.toxml(), 
                  'geni_slivers': geni_slivers}
        
        return result

    def get_instances(self, urns):
        # parse slice names and sliver ids
        slice_names=[]
        sliver_ids=[]
        instances=[]
        filter={}

        for urn in urns:
            xrn = OSXrn(xrn=urn)
            if xrn.type == 'slice':
                slice_names.append(xrn.get_slicename())
            elif xrn.type == 'sliver':
                sliver_ids.append(xrn.leaf) 
        
        # look up instances
        for slice_name in slice_names:
            filter['name'] = slice_name
            servers = self.driver.shell.compute_manager.servers.findall(**filter)
            instances.extend(servers)
        for sliver_id in sliver_ids:
            filter['id'] = sliver_id
            servers = self.driver.shell.compute_manager.servers.findall(**filter)
            instances.extend(servers)
        
        return list(set(instances))

    def instance_to_rspec_node(self, instance):
        # determine node urn
        node_xrn = instance.metadata.get('component_id')
        if not node_xrn:
            node_xrn = OSXrn('cloud', type='node')
        else:
            node_xrn = OSXrn(xrn=node_xrn, type='node')

        rspec_node = NodeElement()
        rspec_node['component_id'] = node_xrn.urn
        rspec_node['component_name'] = node_xrn.name
        rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
        rspec_node['sliver_id'] = OSXrn(name=instance.name, type='slice', id=instance.id).get_urn() 
        if instance.metadata.get('client_id'):
            rspec_node['client_id'] = instance.metadata.get('client_id')

        # get sliver details
        flavor = self.driver.shell.compute_manager.flavors.find(id=instance.flavor['id'])
        sliver = self.instance_to_sliver(flavor)
        # get firewall rules
        fw_rules = []
        group_name = instance.metadata.get('security_groups')
        if group_name:
            group = self.driver.shell.compute_manager.security_groups.find(name=group_name)
            for rule in group.rules:
                # The fw_rule is used by plos namespace
                port_range ="%s:%s" % (rule['from_port'], rule['to_port'])
                if rule['ip_protocol'] is None:
                    rule['ip_protocol'] = 'Any'
                if not rule['ip_range']:
                    rule['ip_range'] = '0.0.0.0/0'
                else:
                    ip_range = rule['ip_range']
                    for key in ip_range:
                        rule['ip_range'] = ip_range[key]
                fw_rule = FWRule({'protocol': rule['ip_protocol'],
                                  'port_range': port_range,
                                  'cidr_ip': rule['ip_range']})
                fw_rules.append(fw_rule)
        sliver['fw_rules'] = fw_rules 
        rspec_node['slivers'] = [sliver]
        
        # get disk image
        image = self.driver.shell.compute_manager.images.get(image=instance.image['id'])
        if isinstance(image, list) and len(image) > 0:
            image = image[0]
        disk_image = os_image_to_rspec_disk_image(image)
        sliver['disk_image'] = [disk_image]

        # get interfaces            
        rspec_node['services'] = []
        rspec_node['interfaces'] = []
        addresses = instance.addresses
        
        if addresses.get('private'):
            login = Login({'authentication': 'ssh-keys',
                           'hostname': addresses.get('private')[-1]['addr'],
                           'port':'22', 'username': 'root'})
            service = ServicesElement({'login': login})
            rspec_node['services'].append(service)    
        
        for private_ip in addresses.get('private', []):
            if_xrn = PlXrn(auth=self.driver.hrn, 
                           interface='node%s' % (instance.hostId)) 
            if_client_id = Xrn(if_xrn.urn, type='interface').urn
            if_sliver_id = Xrn(rspec_node['sliver_id'], type='slice').urn
            interface = Interface({'component_id': if_xrn.urn,
                                   'client_id': if_client_id,
                                   'sliver_id': if_sliver_id})
            interface['ipv4'] = private_ip['addr']
            interface['mac_address'] = private_ip['OS-EXT-IPS-MAC:mac_addr'] 
            rspec_node['interfaces'].append(interface) 
       
        # slivers always provide the ssh service
#        for public_ip in addresses.get('public', []):
#            login = Login({'authentication': 'ssh-keys', 
#                           'hostname': public_ip['addr'], 
#                           'port':'22', 'username': 'root'})
#            service = Services({'login': login})
#            rspec_node['services'].append(service)
        return rspec_node


    def instance_to_sliver(self, instance, xrn=None):
        sliver_id = OSXrn(name = instance.name, type  = 'sliver', id=instance.id).get_urn()
        if xrn:
            sliver_hrn = '%s.%s' % (self.driver.hrn, instance.id)
            sliver_id = Xrn(sliver_hrn, type='sliver').urn

        sliver = Sliver({'sliver_id': sliver_id,
                         'name': instance.name,
                         'type': instance.name,
                         'cpus': str(instance.vcpus),
                         'memory': str(instance.ram),
                         'storage':  str(instance.disk)})
        return sliver   

    def instance_to_geni_sliver(self, instance, sliver_allocations=None):
        if sliver_allocations is None: sliver_allocations={}
        sliver_hrn = '%s.%s' % (self.driver.hrn, instance.id)
        sliver_id = Xrn(sliver_hrn, type='sliver').urn
        
        # set sliver allocation and operational status
        sliver_allocation = sliver_allocations[instance.id]
        expires = sliver_allocation.expiration

        error = ''
        if sliver_allocation:
            allocation_status = sliver_allocation.allocation_state
            if allocation_status == 'geni_allocated':
                op_status =  'geni_pending_allocation'
            elif allocation_status == 'geni_provisioned':
                state = instance.status.lower()
                if state == 'active':
                    op_status = 'geni_ready'
                elif state == 'build':
                    op_status = 'geni_notready'
                elif state == 'error':
#                elif state == 'failed':
                    op_status =' geni_failed'
                    error = "The sliver(s) is/are in error"
                else:
                    op_status = 'geni_unknown'
            else:
                allocation_status = 'geni_unallocated'    
       
        instance_created_time = datetime_to_epoch(utcparse(instance.created))
        geni_sliver = {'geni_sliver_urn': sliver_id, 
                       'geni_expires': expires,
                       'geni_allocation_status': allocation_status,
                       'geni_operational_status': op_status,
                       'geni_error': error,
#                       'geni_error': '',
                       'koren_os_created_time': datetime_to_string(utcparse(instance_created_time)),
                       'koren_os_sliver_type': self.driver.shell.compute_manager.flavors.find(id=instance.flavor['id']).name
                        }
        return geni_sliver
                        
    def get_aggregate_nodes(self):
        zones = self.get_availability_zones()

        # available sliver/instance/vm types
        instances = self.driver.shell.compute_manager.flavors.list()
        if isinstance(instances, dict):
            instances = instances.values()

        # available images
        images = self.driver.shell.compute_manager.images.list()
        disk_images = []
        for image in images:
            if ((image.name.find('ramdisk') == -1) and (image.name.find('kernel') == -1)):
                disk_images.append(os_image_to_rspec_disk_image(image))

        rspec_nodes = []
        for zone in zones:
            rspec_node = NodeElement()
            xrn = OSXrn(self.driver.hrn+'.'+zone, type='node')
#            xrn = OSXrn(zone, type='node')
            rspec_node['component_id'] = xrn.urn
            rspec_node['component_name'] = xrn.name
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['exclusive'] = 'false'
#            rspec_node['hardware_types'] = [HardwareType({'name': 'plos-pc'}),
#                                                HardwareType({'name': 'pc'})]
            slivers = []
            for instance in instances:
                sliver = self.instance_to_sliver(instance,xrn)
                sliver['disk_image'] = disk_images
                slivers.append(sliver)
            rspec_node['available'] = 'true'
            rspec_node['slivers'] = slivers
            rspec_nodes.append(rspec_node) 

        return rspec_nodes 

    def create_network(self, tenant_id):
        is_network = True
        networks = self.driver.shell.network_manager.list_networks()
        networks = networks['networks']
        for network in networks:
            if network.get('tenant_id') == tenant_id:
                network_id = network.get('id')
                net_info = self.driver.shell.network_manager.show_network(network_id)
                net_dict = net_info['network']
                is_network = False

        time.sleep(5)  # This reason for waiting is that OS can't quickly handle "create API". 
        if is_network:
#            ph_int = 'ph-eth1'
#            seg_id = 100
            # create a new network
            n_body = {'network': {'name': 'private', 'tenant_id': tenant_id, 
#                                  'provider:network_type': 'vlan','provider:physical_network': ph_int, 
#                                  'provider:segmentation_id': seg_id
                                 }}
            new_net = self.driver.shell.network_manager.create_network(body=n_body)
            net_dict = new_net['network']
            logger.info("Created a network [%s] as below" % net_dict['name'])
            logger.info(net_dict)

            network_id = net_dict['id']
            cidr = '10.0.0.0/24'
            gw_ip = '10.0.0.1'
            dns_server_ips = ['163.126.63.1', '8.8.8.8']
            alloc_start = '10.0.0.10'
            alloc_end = '10.0.0.20'
            # create a new subnet for network
            sn_body = {'subnets': [{'name': 'private-subnet', 'cidr': cidr, 
                                    'tenant_id': tenant_id, 'network_id': network_id, 
                                    'ip_version': 4, 'enable_dhcp': True,
                                    'gateway_ip': gw_ip, 'dns_nameservers': dns_server_ips,
                                    'allocation_pools': [{'start': alloc_start, 'end': alloc_end}]}]}
            new_subnet = self.driver.shell.network_manager.create_subnet(body=sn_body)
            logger.info("Created a subnet of network [%s] as below" % net_dict['name'])
            logger.info(new_subnet)

        return net_dict
    
    def create_router(self, tenant_id):
        is_router = True
        # checking whether the created router exist
        routers = self.driver.shell.network_manager.list_routers()
        routers = routers['routers']
        for router in routers:
            if router.get('tenant_id') == tenant_id:
                router_id = router.get('id')
                router = self.driver.shell.network_manager.show_router(router_id)
                is_router = False
        
        if is_router:
            # find the network information related with a new interface
            networks = self.driver.shell.network_manager.list_networks()
            networks = networks['networks']
            for network in networks:
                if network.get('name') == 'public':
                    pub_net_id = network.get('id')

            subnets = self.driver.shell.network_manager.list_subnets()
            subnets = subnets['subnets']
            for subnet in subnets:
                if (subnet.get('name') == 'private-subnet') and (subnet.get('tenant_id') == tenant_id):
                    pri_sbnet_id = subnet.get('id')

            # create a router and connect external gateway related with public network
            r_body = {'router': {'name': 'router', 'admin_state_up': True,
                                 'external_gateway_info':{'network_id': pub_net_id}}}
            router = self.driver.shell.network_manager.create_router(body=r_body)
            
            # create a internal port of the router
            router_id = router['router']['id']
            int_pt_body = {'subnet_id': pri_sbnet_id}
            int_port = self.driver.shell.network_manager.add_interface_router(
                                                         router=router_id, body=int_pt_body)
            logger.info("Created a router with interfaces")

        return router

    def create_tenant(self, tenant_name, description=None):
        tenants = self.driver.shell.auth_manager.tenants.findall(name=tenant_name)
        if not tenants:
            tenant = self.driver.shell.auth_manager.tenants.create(tenant_name, description)
        else:
            tenant = tenants[0]
        return tenant

    def create_user(self, user_name, password, tenant_id, email=None, enabled=True):
        if password is None:
            logger.warning("If you want to make a user, you should include your password!!")
            raise ValueError('You should include your password!!')

        users = self.driver.shell.auth_manager.users.findall()
        for user in users:
            if user_name == user.name:
                user_info = user
                logger.info("The user name[%s] already exists." % user_name)
                break
        else:
            user_info = self.driver.shell.auth_manager.users.create(user_name, password, \
                                                                    email, tenant_id, enabled)
        return user_info

    """ KOREN: We don't need this function
    def create_instance_key(self, slice_hrn, user):
        slice_name = Xrn(slice_hrn).leaf
        user_name = Xrn(user['urn']).leaf
        key_name = "%s_%s" % (slice_name, user_name)
        pubkey = user['keys'][0]
        key_found = False
        existing_keys = self.driver.shell.compute_manager.keypairs.findall(name=key_name)
        for existing_key in existing_keys:
            if existing_key.public_key != pubkey:
                self.driver.shell.compute_manager.keypairs.delete(key=existing_key)
            elif existing_key.public_key == pubkey:
                key_found = True
        if not key_found:
            self.driver.shell.compute_manager.keypairs.create(name=key_name, public_key=pubkey)
        return key_name       
    """ 

    def create_security_group(self, slicename, fw_rules=None):
        if fw_rules is None: fw_rules=[]
        # use default group by default
        group_name = 'default' 
        if isinstance(fw_rules, list) and fw_rules:
            # Each sliver get's its own security group.
            # Keep security group names unique by appending some random
            # characters on end.
            random_name = "".join([random.choice(string.letters+string.digits)
                                           for i in xrange(6)])
            group_name = slicename + random_name 
            security_group = SecurityGroup(self.driver)
            security_group.create_security_group(group_name)
            for rule in fw_rules:
                security_group.add_rule_to_group(group_name, 
                                             protocol = rule.get('protocol'), 
                                             cidr_ip = rule.get('cidr_ip'), 
                                             port_range = rule.get('port_range'), 
                                             icmp_type_code = rule.get('icmp_type_code'))
            # Open ICMP by default
            security_group.add_rule_to_group(group_name,
                                             protocol = "icmp",
                                             cidr_ip = "0.0.0.0/0",
                                             icmp_type_code = "-1:-1")
        return group_name

    def add_rule_to_security_group(self, group_name, **kwds):
        security_group = SecurityGroup(self.driver)
        security_group.add_rule_to_group(group_name=group_name, 
                                         protocol=kwds.get('protocol'), 
                                         cidr_ip =kwds.get('cidr_ip'), 
                                         icmp_type_code = kwds.get('icmp_type_code'))

    def check_floatingip(self, instances, value):
        servers = []
        # True: Find servers which not assigned floating IPs
        if value is True:
            for instance in instances:
                for addr in instance.addresses.get('private', []): 
                    if addr.get('OS-EXT-IPS:type') == 'floating':
                        break
                else:
                    servers.append(instance)
        # False: Find servers which assigned floating IPs
        else:
            for instance in instances:
                for addr in instance.addresses.get('private', []):
                    if addr.get('OS-EXT-IPS:type') == 'floating':
                        servers.append(instance)
        return servers 

    def create_floatingip(self, tenant_name, instances):
        tenant = self.driver.shell.auth_manager.tenants.find(name=tenant_name)
        networks = self.driver.shell.network_manager.list_networks().get('networks')
        for network in networks:
            if network.get('name') == 'public':
                pub_net_id = network.get('id')
                break
        else:
            logger.warning("We shoud need the public network ID for floating IPs!")
            raise ValueError("The public network ID was not found!")
        ports = self.driver.shell.network_manager.list_ports().get('ports')
        for port in ports:
            device_id = port.get('device_id')
            for instance in instances:
                if device_id == instance.id:
                    body = { "floatingip":
                             { "floating_network_id": pub_net_id,
                               "tenant_id": tenant.id,
                               "port_id": port.get('id') } }
                    self.driver.shell.network_manager.create_floatingip(body=body)

    def delete_floatingip(self, instances):
        floating_ips = self.driver.shell.network_manager.list_floatingips().get('floatingips')
        for ip in floating_ips:
            ip_tenant_id = ip.get('tenant_id')
            for instance in instances:
                if ip_tenant_id == instance.tenant_id:
                    self.driver.shell.network_manager.delete_floatingip(floatingip=ip.get('id'))

    def check_server_status(self, server):
        while (server.status.lower() == 'build'):
            time.sleep(0.5)
            server = self.driver.shell.compute_manager.servers.findall(id=server.id)[0]
        return server

    def run_instances(self, instance_name, tenant_name, user_name, rspec, expiration, key_name, pubkeys):
        #logger.debug('Reserving an instance: image: %s, flavor: ' \
        #            '%s, key: %s, name: %s' % \
        #            (image_id, flavor_id, key_name, slicename))
        # make sure a tenant exists for this slice

        # It'll use Openstack admin info. as authoirty
        zones = self.get_availability_zones()
        zone = zones[0]

        # add the sfa admin user to this tenant and update your OpenStack client connection
        # to use these credentials for the rest of this session. This emsures that the instances
        # we create will be assigned to the correct tenant.
        auth_name, pwd = self.driver.find_user_info(user_name=user_name)
#        local_users = self.driver.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
        self.driver.shell.network_manager.connect(username=user_name, tenant=tenant_name, password=pwd)

        logger.info("Checking if the created tenant[%s] or not ..." % tenant_name)
        tenant = self.driver.shell.auth_manager.tenants.find(name=tenant_name)
        
        if len(pubkeys):
            files = None
        else:
            authorized_keys = "\n".join(pubkeys)
            files = {'/root/.ssh/authorized_keys': authorized_keys}
        net_dict = self.create_network(tenant_id=tenant.id)
        router = self.create_router(tenant_id=tenant.id)
        nics=[{'net-id': net_dict['id']}]

        # iterate over clouds/zones/nodes
        dbsession=self.driver.api.dbsession()
        slivers = []
        rspec = RSpec(rspec)
        for node in rspec.version.get_nodes_with_slivers():
            instances = node.get('slivers', [])
            if not instances:
                continue
            for instance in instances:
                try: 
                    metadata = {}
                    flavor_id = self.driver.shell.compute_manager.flavors.find(name=instance['name'])
                    image = instance.get('disk_image')
                    if image and isinstance(image, list):
                        image = image[0]
                    else:
                        raise InvalidRSpec("Must specify a disk_image for each VM")
                    image_id = self.driver.shell.compute_manager.images.find(name=image['name'])
                    fw_rules = instance.get('fw_rules', [])
                    group_name = self.create_security_group(instance_name, fw_rules)
                    metadata['security_groups'] = group_name
                    if node.get('component_id'):
                        metadata['component_id'] = node['component_id']
                    if node.get('client_id'):
                        metadata['client_id'] = node['client_id'] 
                   
                    server = self.driver.shell.compute_manager.servers.create(
                                                               flavor=flavor_id,
                                                               image=image_id,
                                                               nics=nics,
                                                               availability_zone=zone,
                                                               key_name=key_name,
                                                               security_groups=[group_name],
                                                               files=files,
                                                               meta=metadata, 
                                                               name=instance_name)
                    server = self.check_server_status(server)
                    slivers.append(server)
                    SliverAllocation.set_allocates_expires(server, 'geni_allocated', \
                                                           expiration, dbsession)
                    logger.info("Created Openstack instance [%s]" % instance_name)

                except Exception, err:    
                    logger.log_exc(err)
        
        logger.info("Completed slivers: %s" % slivers)                    
        return slivers        

    def delete_instance(self, instance):
    
        def _delete_security_group(inst):
            security_group = inst.metadata.get('security_groups', '')
            if security_group:
                manager = SecurityGroup(self.driver)
                timeout = 10.0 # wait a maximum of 10 seconds before forcing the security group delete
                start_time = time.time()
                instance_deleted = False
                while instance_deleted == False and (time.time() - start_time) < timeout:
                    tmp_inst = self.driver.shell.compute_manager.servers.findall(id=inst.id)
                    if not tmp_inst:
                        instance_deleted = True
                    time.sleep(.5)
                manager.delete_security_group(security_group)
        
        multiclient = MultiClient()
        tenant = self.driver.shell.auth_manager.tenants.find(id=instance.tenant_id)

        # Update Openstack connection info.
        user_name, tenant_name = self.driver.find_slice_info(slice_urn=tenant.name)
#        local_slices = self.driver.api.dbsession().query(RegRecord).filter_by(type='slice').all()
#        for slice in local_slices:
#            if tenant.name == slice.os_slice_nm:
#                tenant_name = tenant.name       
#                user_name = slice.os_user_nm
#                break
#        else:
#            slice_xrn = Xrn(hrn_to_urn(tenant.name, 'slice'))
#            tenant_name = slice_xrn.get_hrn()
#            user_name = slice_xrn.get_authority_hrn() + '.' + slice_xrn.leaf.split('-')[0]
        auth_name, pwd = self.driver.find_user_info(user_name=user_name)
#        local_users = self.driver.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
        args = {'name': instance.name,
                'id': instance.id}
        instances = self.driver.shell.compute_manager.servers.findall(**args)
        security_group_manager = SecurityGroup(self.driver)
        for instance in instances:
            # destroy instance
            self.driver.shell.compute_manager.servers.delete(instance)
            # deleate this instance's security groups
            multiclient.run(_delete_security_group, instance)
        return 1

    def delete_router(self, tenant_id):
        is_router = False
        ports = self.driver.shell.network_manager.list_ports()
        ports = ports['ports']
        networks = self.driver.shell.network_manager.list_networks()
        networks = networks['networks']

        # find the subnetwork ID for removing the interface related with private network
        # TOPOLOGY: Public Network -- Router -- Private Network -- VM Instance(s)
        for port in ports:
            if (port.get('tenant_id') == tenant_id) and \
               (port.get('device_owner') == 'network:router_interface'):
                router_id = port.get('device_id')
                port_net_id = port.get('network_id')
        for network in networks:
            if network.get('tenant_id') == tenant_id:
                net_id = network.get('id')
                if port_net_id == net_id:
                    sbnet_ids = network.get('subnets')
                    is_router = True
        
        if is_router:
            # remove the router's interface which is related with private network
            if sbnet_ids:
                body = {'subnet_id': sbnet_ids[0]}
                self.driver.shell.network_manager.remove_interface_router(
                                                  router=router_id, body=body)
            # remove the router's interface which is related with public network
            self.driver.shell.network_manager.remove_gateway_router(router=router_id)
            # delete the router
            self.driver.shell.network_manager.delete_router(router=router_id)
            logger.info("Deleted the router: Router ID [%s]" % router_id)

        return 1

    def delete_network(self, tenant_id):
        is_network = False
        networks = self.driver.shell.network_manager.list_networks()
        networks = networks['networks']

        # find the network ID and subnetwork ID
        for network in networks:
            if network.get('tenant_id') == tenant_id:
                net_id = network.get('id')
                sbnet_ids = network.get('subnets')
                is_network = True
                
        time.sleep(5)  # This reason for waiting is that OS can't quickly handle "delete API". 
        if is_network:
            # delete the subnetwork and then finally delete the network related with tenant
            self.driver.shell.network_manager.delete_subnet(subnet=sbnet_ids[0])
            self.driver.shell.network_manager.delete_network(network=net_id)
            logger.info("Deleted the network: Network ID [%s]" % net_id)

        return 1

    def stop_instances(self, instance_name, tenant_name, id=None):
        # Update OpenStack connection
        slices = self.driver.api.dbsession().query(RegRecord).filter_by(type='slice').all()
        for slice in slices:
            if tenant_name == slice.os_slice_nm:
                user_name = slice.os_user_nm
                break
        else:
            slice_xrn = Xrn(hrn_to_urn(tenant_name, 'slice'))
            user_name = slice_xrn.get_authority_hrn() + '.' + slice_xrn.leaf.split('-')[0]
        users = self.driver.api.dbsession().query(RegRecord).filter_by(type='user').all()
        for user in users:
            if user_name == user.os_user_nm:
                pwd = user.os_user_pw
                break
        else:
            pwd = user_name
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
        args = {'name': instance_name}
        if id:
            args['id'] = id
        instances = self.driver.shell.compute_manager.servers.findall(**args)
        for instance in instances:
            self.driver.shell.compute_manager.servers.pause(instance)
        return 1

    def start_instances(self, instance_name, tenant_name, id=None):
        # Update OpenStack connection
        user_name, tenant_name = self.driver.find_slice_info(slice_urn=tenant_name)
#        local_slices = self.driver.api.dbsession().query(RegRecord).filter_by(type='slice').all()
#        for slice in local_slices:
#            if tenant_name == slice.os_slice_nm:
#                user_name = slice.os_user_nm
#                break
#        else:
#            slice_xrn = Xrn(hrn_to_urn(tenant_name, 'slice'))
#            user_name = slice_xrn.get_authority_hrn() + '.' + slice_xrn.leaf.split('-')[0]
        auth_name, pwd = self.driver.find_user_info(user_name=user_name)
#        local_users = self.driver.api.dbsession().query(RegRecord).filter_by(type='user').all()
#        for user in local_users:
#            if user_name == user.os_user_nm:
#                pwd = user.os_user_pw
#                break
#        else:
#            pwd = user_name
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=pwd)
        args = {'name': instance_name}
        if id:
            args['id'] = id
        instances = self.driver.shell.compute_manager.servers.findall(**args)
        for instance in instances:
            self.driver.shell.compute_manager.servers.resume(instance)
        return 1

    def restart_instances(self, instacne_name, tenant_name, id=None):
        self.stop_instances(instance_name, tenant_name, id)
        self.start_instances(instance_name, tenant_name, id)
        return 1 

    def update_instances(self, project_name):
        pass
