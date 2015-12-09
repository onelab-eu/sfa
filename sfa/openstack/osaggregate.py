######################################################################################################
# Edited on Jun 20, 2015                                                                             #
# Code modified by Chaima Ghribi.                                                                    #
# The original code is available on github at https://github.com/onelab-eu/sfa/tree/openstack-driver.#
# Modifications are noted as comments in the code itself.                                            #
# @contact: chaima.ghribi@it-sudparis.eu                                                             #
# @organization: Institut Mines-Telecom - Telecom SudParis                                           #
######################################################################################################

import os
import socket
import base64
import string
import random
import time    
from collections import defaultdict
from sfa.util.faults import SliverDoesNotExist
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, get_leaf, hrn_to_urn
from sfa.util.sfalogging import logger
from sfa.storage.model import SliverAllocation

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.openstack import *
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.elements.node import NodeElement

from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.services import ServicesElement

from sfa.client.multiclient import MultiClient
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename
from sfa.openstack.security_group import SecurityGroup
from sfa.openstack.osconfig import OSConfig

# for exception
from novaclient import exceptions

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
    img = OSImage()
    img['name']    = str(image.name)
    img['minDisk'] = str(image.minDisk)
    img['minRam']  = str(image.minRam)
    img['imgSize'] = str(image._info['OS-EXT-IMG-SIZE:size'])
    img['status']  = str(image.status)
    return img
    
class OSAggregate:

    def __init__(self, driver):
        logger.debug("start OS DRIVER")
        self.driver = driver

    def get_availability_zones(self, zones=None):
        # Update inital connection info
        self.driver.init_compute_manager_conn()
        zone_list=[]
        if not zones:
            availability_zones = self.driver.shell.compute_manager.availability_zones.list()
            for zone in availability_zones:
                if (zone.zoneState.get('available') == True) and \
                   (zone.zoneName != 'internal'):
                    zone_list.append(zone.zoneName)
        else:
            availability_zones = self.driver.shell.compute_manager.availability_zones.list()
            for a_zone in availability_zones:
                for i_zone in zones:
                    if a_zone.zoneName == i_zone: 
                        if (a_zone.zoneState.get('available') == True) and \
                           (a_zone.zoneName != 'internal'):
                            zone_list.append(a_zone.zoneName)
        return zone_list

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

        # Update connection for the current user
        xrn = Xrn(urns[0], type='slice')
        #user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        tenant_name = OSXrn(xrn=urns[0], type='slice').get_hrn()
        user_name = options['actual_caller_hrn']
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)

        # For delay to collect instance info 
        time.sleep(3)
        # Get instances from the Openstack
        instances = self.get_instances(xrn)

        # Add sliver(s) from instance(s)
        geni_slivers = []
        rspec.xml.set( 'expires',  datetime_to_string(utcparse(time.time())) )
        rspec_nodes = []
        for instance in instances:
            rspec_nodes.append(self.instance_to_rspec_node(instance))
            geni_sliver = self.instance_to_geni_sliver(instance)
            geni_slivers.append(geni_sliver)
        rspec.version.add_nodes(rspec_nodes)

        result = { 'geni_urn': xrn.get_urn(),
                   'geni_rspec': rspec.toxml(), 
                   'geni_slivers': geni_slivers }
        return result

    def get_instances(self, xrn):
        # parse slice names and sliver ids
        slice_names=[]
        sliver_ids=[]
        instances=[]
        if xrn.type == 'slice':
            slice_names.append(xrn.get_hrn())
        else:
            print "[WARN] We don't know the xrn[%s]" % xrn.type
            logger.warn("[WARN] We don't know the xrn[%s], Check it!" % xrn.type)
            
        try:
            # look up instances
            servers = self.driver.shell.compute_manager.servers.findall()

            for slice_name in slice_names:
                servers = self.driver.shell.compute_manager.servers.findall()
                instances.extend(servers)
            for sliver_id in sliver_ids:
                servers = self.driver.shell.compute_manager.servers.findall()
                instances.extend(servers)
        except(exceptions.Unauthorized):
            print "[WARN] The instance(s) in Openstack is/are not permitted."
            logger.warn("The instance(s) in Openstack is/are not permitted.")
            return []
        return list( set(instances) )

    def instance_to_rspec_node(self, instance):
        # determine node urn
        node_xrn = instance.metadata.get('component_id')
        if not node_xrn:
            node_xrn = OSXrn(self.driver.hrn+'.'+'openstack', type='node')
        else:
            node_xrn = OSXrn(xrn=node_xrn, type='node')

        rspec_node = NodeElement()
        if not instance.metadata.get('component_manager_id'):
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, type='authority+am').get_urn()
        else:
            rspec_node['component_manager_id'] = instance.metadata.get('component_manager_id')
        rspec_node['component_id'] = node_xrn.urn
        rspec_node['component_name'] = node_xrn.name
        rspec_node['sliver_id'] = OSXrn(name=(self.driver.api.hrn+'.'+ instance.name), id=instance.id, \
                                        type='node+openstack').get_urn()

        # get sliver details about quotas of resource
        flavor = self.driver.shell.compute_manager.flavors.find(id=instance.flavor['id'])
        sliver = self.flavor_to_sliver(flavor=flavor, instance=instance, xrn=None)
   
        # get availability zone
        zone_name = instance.to_dict().get('OS-EXT-AZ:availability_zone')    
        sliver['availability_zone'] = OSZone({ 'name': zone_name })

        # get firewall rules
        group_names = instance.security_groups
        sliver['security_groups']=[]
        if group_names and isinstance(group_names, list):
            for group in group_names:
                group = self.driver.shell.compute_manager.security_groups.find(name=group.get('name'))
                sliver['security_groups'].append(self.secgroup_to_rspec(group))

        # get disk image from the Nova service
        image = self.driver.shell.compute_manager.images.get(image=instance.image['id'])
        boot_image = os_image_to_rspec_disk_image(image)
        sliver['boot_image'] = boot_image

        # Get addresses of the sliver
        sliver['addresses']=[]
        addresses = instance.addresses
        if addresses:
            from netaddr import IPAddress
            for addr in addresses.get('private'):
                fields = OSSliverAddr({ 'mac_address': addr.get('OS-EXT-IPS-MAC:mac_addr'),
                                        'version': str(addr.get('version')),
                                        'address': addr.get('addr'),
                                        'type': addr.get('OS-EXT-IPS:type') })
                # Check if ip address is local
                ipaddr = IPAddress(addr.get('addr'))
                if (ipaddr.words[0] == 10) or (ipaddr.words[0] == 172 and ipaddr.words[1] == 16) or \
                   (ipaddr.words[0] == 192 and ipaddr.words[1] == 168):
                    type = { 'private': fields }
                else:
                    type = { 'public': fields }
                sliver['addresses'].append(type)

        rspec_node['slivers'] = [sliver]
        return rspec_node

    def secgroup_to_rspec(self, group):
        rspec_rules=[]
        for rule in group.rules:
            rspec_rule =  OSSecGroupRule({ 'ip_protocol': str(rule['ip_protocol']),
                                           'from_port': str(rule['from_port']),
                                           'to_port': str(rule['to_port']),
                                           'ip_range': str(rule['ip_range'])
                                         })
            rspec_rules.append(rspec_rule)

        rspec = OSSecGroup({ 'id': str(group.id),
                             'name': str(group.name),
                             'description': str(group.description),
                             'rules': rspec_rules
                           })
        return rspec

    def flavor_to_sliver(self, flavor, instance=None, xrn=None):
        if xrn:
            sliver_id = OSXrn(name='koren.sliver', type='node+openstack').get_urn()
            sliver_name = None
        if instance:
            sliver_id = OSXrn(name=(self.driver.api.hrn+'.'+ instance.name), id=instance.id, \
                              type='node+openstack').get_urn()
            sliver_name = instance.name
        sliver = OSSliver({ 'sliver_id': str(sliver_id),
                            'sliver_name': str(sliver_name),
                            'sliver_type': 'virtual machine',
                            'flavor': \
                                     OSFlavor({ 'name': str(flavor.name),
                                                'id': str(flavor.id),
                                                'vcpus': str(flavor.vcpus),
                                                'ram': str(flavor.ram),
                                                'storage': str(flavor.disk)
                                              }) })
        return sliver

    def instance_to_geni_sliver(self, instance):
        sliver_id = OSXrn(name=(self.driver.api.hrn+'.'+ instance.name), id=instance.id, \
                          type='node+openstack').get_urn()

        constraint = SliverAllocation.sliver_id.in_([sliver_id])
        sliver_allocations = self.driver.api.dbsession().query(SliverAllocation).filter(constraint)
        sliver_allocation_status = sliver_allocations[0].allocation_state

        error = 'None'
        op_status = 'geni_unknown'
        if sliver_allocation_status:
            if sliver_allocation_status == 'geni_allocated':
                op_status = 'geni_pending_allocation'
            elif sliver_allocation_status == 'geni_provisioned':
                state = instance.status.lower()
                if state == 'active':
                    op_status = 'geni_ready'
                elif state == 'build':
                    op_status = 'geni_not_ready'
                elif state == 'error':
                    op_status = 'geni_failed'
                    error = "Retry to provisioning them!"
                else:
                    op_status = 'geni_unknown'
            elif sliver_allocation_status == 'geni_unallocated':
                op_status = 'geni_not_ready'
        else:
            sliver_allocation_status = 'geni_unknown'

        geni_sliver = { 'geni_sliver_urn': sliver_id, 
                        'geni_expires': None,
                        'geni_allocation_status': sliver_allocation_status,
                        'geni_operational_status': op_status,
                        'geni_error': error,
                        'os_sliver_created_time': instance.created
                      }
        return geni_sliver
                        
    def get_aggregate_nodes(self):
        # Get the list of available zones
        zones = self.get_availability_zones()
        # Get the list of available instance types 
        flavors = self.driver.shell.compute_manager.flavors.list() 
        # Get the list of available instance images
        images = self.driver.shell.compute_manager.images.list()
        available_images=[]
        for image in images:
            if ((image.name.find('ramdisk') == -1) and (image.name.find('kernel') == -1)):
                available_images.append(os_image_to_rspec_disk_image(image))
      
        security_groups=[]
        groups = self.driver.shell.compute_manager.security_groups.list()
        for group in groups:
            security_groups.append(self.secgroup_to_rspec(group))

        rspec_nodes=[]
        for zone in zones:
            rspec_node = NodeElement()
            xrn = Xrn(self.driver.hrn+'.'+'openstack', type='node')
            rspec_node['component_id'] = xrn.urn
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, type='authority+am').get_urn()
            rspec_node['exclusive'] = 'false'

            slivers=[]
            for flavor in flavors:
                sliver = self.flavor_to_sliver(flavor=flavor, instance=None, xrn=xrn)
                sliver['component_id'] = xrn.urn
                sliver['images'] = available_images
                sliver['availability_zone'] = OSZone({ 'name': zone })
                sliver['security_groups'] = security_groups
                slivers.append(sliver)
            rspec_node['slivers'] = slivers
            rspec_node['available'] = 'true'
            rspec_nodes.append(rspec_node)
        
        return rspec_nodes

    def create_network(self, tenant_id):
        logger.info("Enter create_network")
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
            config = OSConfig()
            # Check type of tenant network in Openstack
            type = config.get('network', 'type').lower()
            if type == 'vlan':
                phy_int = config.get('network:vlan', 'physical_network')
                seg_id = int(config.get('network:vlan', 'segmentation_id'))
                n_body = {'network': {'name': 'private', 'tenant_id': tenant_id,
                                      'provider:network_type': 'vlan',
                                      'provider:physical_network': phy_int,
                                      'provider:segmentation_id': seg_id} }
            elif type == 'flat':
                n_body = { 'network': {'name': 'private', 'tenant_id': tenant_id} }
            elif type == 'local':
                n_body = { 'network': {'name': 'private', 'tenant_id': tenant_id} }
            elif type == 'vxlan_gre':
                n_body = { 'network': {'name': 'private', 'tenant_id': tenant_id} }
            else:
                logger.error('You need to write the information in /etc/sfa/network.ini')

            # create a new network
            new_net = self.driver.shell.network_manager.create_network(body=n_body)
            net_dict = new_net['network']
            logger.info("Created a network [%s] as below" % net_dict['name'])
            logger.info(net_dict)

            # Information of subnet from configuration file
            sub_name = config.get('subnet', 'name')
            version = int(config.get('subnet', 'version'))
            cidr = config.get('subnet', 'cidr')
            gw_ip = config.get('subnet', 'gateway_ip')
            dns_servers = config.get('subnet', 'dns_nameservers').split()
            is_dhcp = bool(config.get('subnet', 'enable_dhcp'))
            if is_dhcp is True:
                alloc_start = config.get('subnet', 'allocation_start')
                alloc_end = config.get('subnet', 'allocation_end')
            else:
                alloc_start = None
                alloc_end = None
            network_id = net_dict['id']

            # create a new subnet for network
            sn_body = {'subnets': [{ 'name': sub_name, 'cidr': cidr,
                                     'tenant_id': tenant_id, 'network_id': network_id,
                                     'ip_version': version, 'enable_dhcp': is_dhcp,
                                     'gateway_ip': gw_ip, 'dns_nameservers': dns_servers,
                                     'allocation_pools': [{'start': alloc_start, 'end': alloc_end}] }]}
            new_subnet = self.driver.shell.network_manager.create_subnet(body=sn_body)
            logger.info("Created a subnet of network [%s] as below" % net_dict['name'])
            logger.info(new_subnet)

        return net_dict

    def create_router(self, tenant_id):
        logger.info("Enter create_router function")
        is_router = True
        pub_net_id = None
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

            # Code modified by Chaima Ghribi
            config = OSConfig()
            # Information of public network from configuration file
            public_net_name = config.get('public', 'name')
            logger.info("public_net_name = %s" % public_net_name)
            logger.info("networks = %s" % networks)
            for network in networks:
                logger.info(network.get('name'))
                if network.get('name') == public_net_name:
                    pub_net_id = network.get('id')
            ###
            if pub_net_id is None:
                logger.error("Public network %s not found, Please check /etc/sfa/network.ini configuration of public network" % public_net_name)
            # Information of subnet network name from configuration file
            subnet_name = config.get('subnet', 'name')
            subnets = self.driver.shell.network_manager.list_subnets()
            subnets = subnets['subnets']
            logger.info("subnets = %s" % subnets)
            for subnet in subnets:
                if ((subnet.get('name') == subnet_name) or (subnet.get('name') == 'private-subnet')) and \
                   (subnet.get('tenant_id') == tenant_id):
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

        # Code modified by Chaima Ghribi
        config = OSConfig()
        # Information of public network from configuration file
        public_net_name = config.get('public', 'name')
        for network in networks:
            if network.get('name') == public_net_name:
                pub_net_id = network.get('id')
                break
        ###
        else:
            logger.warning("We shoud need the public network ID for floating IPs!")
            raise ValueError("The public network ID was not found!")
        ports = self.driver.shell.network_manager.list_ports().get('ports')
        for port in ports:
            device_id = port.get('device_id')
            for instance in instances:
                # public ip only if external_ip is set to true
                if 'external_ip' in instance.metadata and instance.metadata['external_ip']=='true' and device_id == instance.id:
                    body = { "floatingip":
                             { "floating_network_id": pub_net_id,
                               "tenant_id": tenant.id,
                               "port_id": port.get('id') } }
                    self.driver.shell.network_manager.create_floatingip(body=body)

    def delete_floatingip(self, instances):
        floating_ips = self.driver.shell.network_manager.list_floatingips().get('floatingips')
        logger.debug("--- delete_floatingip ---")
        logger.debug(floating_ips)
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

    def run_instances(self, tenant_name, user_name, rspec, key_name, pubkeys):
        logger.info("Enter run_instances")
        slivers = []
        try:
            # It'll use Openstack admin info. as authoirty
            zones = self.get_availability_zones()
    
            # add the sfa admin user to this tenant and update our Openstack client connection
            # to use these credentials for the rest of this session. This emsures that the instances
            # XXX Connect Nova client with user and tenant
            # VM we create will be assigned to the correct tenant.
            self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)
            logger.info( "Checking if the created tenant[%s] or not ..." % tenant_name )
            tenant = self.driver.shell.auth_manager.tenants.find(name=tenant_name)

            if len(pubkeys):
                files = None
            else:
                authorized_keys = "\n".join(pubkeys)
                files = {'/root/.ssh/authorized_keys': authorized_keys}

            # XXX Connect Neutron client with user and tenant
            self.driver.shell.network_manager.connect(username=user_name, tenant=tenant_name, password=user_name)
            logger.info("Connect Neutron using username = %s - tenant = %s" % (user_name,tenant_name))
            net_dict = self.create_network(tenant_id=tenant.id)
            router = self.create_router(tenant_id=tenant.id)
            nics=[{'net-id': net_dict['id']}]

            # Iterate over clouds/zones/nodes
            rspec = RSpec(rspec)
            l_rspec_servers = list()
            os_all_instances = self.driver.shell.compute_manager.servers.list()

            l_os_servers = [server.name for server in os_all_instances]
            logger.info("Openstack existing instances %s" % l_os_servers)
            for node in rspec.version.get_nodes_with_slivers():
                instances = node.get('slivers', [])
                for instance in instances:
                    server_name = instance['sliver_name']
                    l_rspec_servers.append(server_name)

                    # Check if instance exists or not
                    if server_name in l_os_servers:
                        logger.info("VM sliver_name = %s already existed in Openstack" % server_name)
                        servers = self.driver.shell.compute_manager.servers.findall(name=server_name)
                        if len(servers) != 0:
                            for server in servers:
                                slivers.append(server)
                            continue

                    flavor = self.driver.shell.compute_manager.flavors.find(name=instance['flavor']['name'])
                    image = self.driver.shell.compute_manager.images.find(name=instance['boot_image']['name'])
                    zone_name = instance['availability_zone']['name']
                    for zone in zones:
                        if zone == zone_name:
                            break
                    else:
                        logger.warn("The requested zone_name[%s] is invalid ... So it's changed " % zone_name)
                        zone_name = zone

                    group_names=[]   
                    for sec_group in self.driver.secgroups_with_rules(instance['security_groups']):
                        group_names.append(sec_group.name)

                    metadata = {}
                    if node.get('component_id'):
                        metadata['component_id'] = node['component_id']
                    if node.get('component_manager_id'):
                        metadata['component_manager_id'] = node['component_manager_id']

                    # If external_ip = true this VM will get a public IP with Provision
                    if node.get('external_ip'):
                        metadata['external_ip'] = node['external_ip']
                    else:
                        metadata['external_ip'] = "false"

                    # Create a server for the user
                    server = self.driver.shell.compute_manager.servers.create(
                                                               flavor=flavor.id,
                                                               image=image.id,
                                                               nics=nics,
                                                               availability_zone=zone_name,
                                                               key_name=key_name,
                                                               security_groups=group_names,
                                                               meta=metadata,
                                                               name=server_name,
                                                               files=files)
                    server = self.check_server_status(server)
                    slivers.append(server)
                    logger.info("Created Openstack instance [%s]" % server_name)

            # Delete instances that are not in the RSpec but are still exsiting in Openstack
            l_delete_servers = set(l_os_servers).difference(l_rspec_servers)
            for server_name in l_delete_servers:
                for server in os_all_instances:
                    if server.name == server_name:
                        server_instance = server
                        break
                logger.info("Delete Openstack instance [%s]" % server_name)
                self.driver.shell.compute_manager.servers.delete(server_instance)
        except Exception, err:
            logger.log_exc(err)

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
        
        # Update connection for the current client
        xrn = Xrn(tenant.name)

        # Code modified by Chaima Ghribi
        user_name = tenant.description
        ###

        args = { 'name': instance.name,
                 'id': instance.id }
        instances = self.driver.shell.compute_manager.servers.findall(**args)
        security_group_manager = SecurityGroup(self.driver)
        for instance in instances:
            # destroy instance
            self.driver.shell.compute_manager.servers.delete(instance)
            logger.info("Deleted instance = %s" % instance)
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
                port_id = port.get('id')

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

    def delete_tenant(self, tenant_id):
        try:
            tenants = self.driver.shell.auth_manager.tenants.findall(id=tenant_id)
            logger.info("Deleting tenants = [%s]" % tenants)
            if len(tenants) != 0:
                for tenant in tenants:
                    self.driver.shell.auth_manager.tenants.delete(tenant)
                    logger.info("Deleted tenant = %s" % tenant)
        except Exception, err:
            logger.log_exc(err)
        
    def stop_instances(self, instance_name, tenant_name, id=None):
        # Update connection for the current client
        xrn = Xrn(tenant_name)
        user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)

        args = { 'name': instance_name }
        if id:
            args['id'] = id
        instances = self.driver.shell.compute_manager.servers.findall(**args)
        for instance in instances:
            self.driver.shell.compute_manager.servers.pause(instance)
        return 1

    def start_instances(self, instance_name, tenant_name, id=None):
        # Update connection for the current client
        xrn = Xrn(tenant_name)
        user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)

        args = { 'name': instance_name }
        if id:
            args['id'] = id
        instances = self.driver.shell.compute_manager.servers.findall(**args)
        for instance in instances:
            self.driver.shell.compute_manager.servers.resume(instance)
        return 1

    def restart_instances(self, instacne_name, tenant_name, id=None):
        # Update connection for the current client
        xrn = Xrn(tenant_name)
        user_name = xrn.get_authority_hrn() + '.' + xrn.leaf.split('-')[0]
        self.driver.shell.compute_manager.connect(username=user_name, tenant=tenant_name, password=user_name)

        self.stop_instances(instance_name, tenant_name, id)
        self.start_instances(instance_name, tenant_name, id)
        return 1 

    def update_instances(self, project_name):
        pass
