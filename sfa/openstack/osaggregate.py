
import os
import socket
import base64
import string
import random
import time
from collections import defaultdict
from nova.exception import ImageNotFound
from nova.api.ec2.cloud import CloudController
from sfa.util.faults import SfaAPIError, InvalidRSpec
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.disk_image import DiskImage
from sfa.rspecs.elements.services import Services
from sfa.rspecs.elements.interface import Interface
from sfa.util.xrn import Xrn
from sfa.planetlab.plxrn import PlXrn 
from sfa.openstack.osxrn import OSXrn, hrn_to_os_slicename
from sfa.rspecs.version_manager import VersionManager
from sfa.openstack.security_group import SecurityGroup
from sfa.server.threadmanager import ThreadManager
from sfa.util.sfalogging import logger

def pubkeys_to_user_data(pubkeys):
    user_data = "#!/bin/bash\n\n"
    for pubkey in pubkeys:
        pubkey = pubkey.replace('\n', '')
        user_data += "echo %s >> /root/.ssh/authorized_keys" % pubkey
        user_data += "\n"
        user_data += "echo >> /root/.ssh/authorized_keys"
        user_data += "\n"
    return user_data

def instance_to_sliver(instance, slice_xrn=None):
    sliver_id = None
    sliver = Sliver({'name': instance.name,
                     'type': instance.name,
                     'cpus': str(instance.vcpus),
                     'memory': str(instance.ram),
                     'storage':  str(instance.disk)})
    return sliver

def image_to_rspec_disk_image(image):
    img = DiskImage()
    img['name'] = image['name']
    img['description'] = image['name']
    img['os'] = image['name']
    img['version'] = image['name']    
    return img
    
class OSAggregate:

    def __init__(self, driver):
        self.driver = driver

    def get_rspec(self, slice_xrn=None, version=None, options={}):
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')
            nodes = self.get_aggregate_nodes()
        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
            nodes = self.get_slice_nodes(slice_xrn)
        rspec = RSpec(version=rspec_version, user_options=options)
        rspec.version.add_nodes(nodes)
        return rspec.toxml()

    def get_availability_zones(self):
        # essex release
        zones = self.driver.shell.nova_manager.dns_domains.domains()

        if not zones:
            zones = ['cloud']
        else:
            zones = [zone.name for zone in zones]
        return zones

    def get_slice_nodes(self, slice_xrn):
        # update nova connection
        tenant_name = OSXrn(xrn=slice_xrn, type='slice').get_tenant_name()
        self.driver.shell.nova_manager.connect(tenant=tenant_name)    
        
        zones = self.get_availability_zones()
        name = hrn_to_os_slicename(slice_xrn)
        instances = self.driver.shell.nova_manager.servers.findall(name=name)
        rspec_nodes = []
        for instance in instances:
            # determine node urn
            node_xrn = instance.metadata.get('component_id')
            if not node_xrn:
                node_xrn = OSXrn('cloud', type='node')
            else:
                node_xrn = OSXrn(xrn=node_xrn, type='node')

            rspec_node = Node()
            rspec_node['component_id'] = node_xrn.urn
            rspec_node['component_name'] = node_xrn.name
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['slivers'] = []

            if instance.metadata.get('client_id'):
                rspec_node['client_id'] = instance.metadata.get('client_id')
            
            flavor = self.driver.shell.nova_manager.flavors.find(id=instance.flavor['id'])
            sliver = instance_to_sliver(flavor)
            rspec_node['slivers'].append(sliver)
            sliver_xrn = OSXrn(xrn=slice_xrn, type='slice', id=instance.id)
            rspec_node['sliver_id'] = sliver_xrn.get_urn()
            image = self.driver.shell.image_manager.get_images(id=instance.image['id'])
            if isinstance(image, list) and len(image) > 0:
                image = image[0]
            disk_image = image_to_rspec_disk_image(image)
            sliver['disk_image'] = [disk_image]

            # build interfaces            
            rspec_node['services'] = []
            rspec_node['interfaces'] = []
            addresses = instance.addresses
            # HACK: public ips are stored in the list of private, but 
            # this seems wrong. Assume pub ip is the last in the list of 
            # private ips until openstack bug is fixed.      
            if addresses.get('private'):
                login = Login({'authentication': 'ssh-keys',
                               'hostname': addresses.get('private')[-1]['addr'],
                               'port':'22', 'username': 'root'})
                service = Services({'login': login})
                rspec_node['services'].append(service)    
            
            for private_ip in addresses.get('private', []):
                if_xrn = PlXrn(auth=self.driver.hrn, 
                               interface='node%s' % (instance.hostId)) 
                if_client_id = Xrn(if_xrn.urn, type='interface', id="eth%s" %if_index).urn
                interface = Interface({'component_id': if_xrn.urn,
                                       'client_id': if_client_id})
                interface['ips'] =  [{'address': private_ip['addr'],
                                     #'netmask': private_ip['network'],
                                     'type': 'ipv%s' % str(private_ip['version'])}]
                rspec_node['interfaces'].append(interface) 
            
            # slivers always provide the ssh service
            for public_ip in addresses.get('public', []):
                login = Login({'authentication': 'ssh-keys', 
                               'hostname': public_ip['addr'], 
                               'port':'22', 'username': 'root'})
                service = Services({'login': login})
                rspec_node['services'].append(service)
            rspec_nodes.append(rspec_node)
        return rspec_nodes

    def get_aggregate_nodes(self):
        zones = self.get_availability_zones()
        # available sliver/instance/vm types
        instances = self.driver.shell.nova_manager.flavors.list()
        if isinstance(instances, dict):
            instances = instances.values()
        # available images
        images = self.driver.shell.image_manager.get_images_detailed()
        disk_images  = [image_to_rspec_disk_image(img) for img in images if img['container_format'] in ['ami', 'ovf']]
        rspec_nodes = []
        for zone in zones:
            rspec_node = Node()
            xrn = OSXrn(zone, type='node')
            rspec_node['component_id'] = xrn.urn
            rspec_node['component_name'] = xrn.name
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['exclusive'] = 'false'
            rspec_node['hardware_types'] = [HardwareType({'name': 'plos-pc'}),
                                                HardwareType({'name': 'pc'})]
            slivers = []
            for instance in instances:
                sliver = instance_to_sliver(instance)
                sliver['disk_image'] = disk_images
                slivers.append(sliver)
        
            rspec_node['slivers'] = slivers
            rspec_nodes.append(rspec_node) 

        return rspec_nodes 


    def create_tenant(self, tenant_name):
        tenants = self.driver.shell.auth_manager.tenants.findall(name=tenant_name)
        if not tenants:
            self.driver.shell.auth_manager.tenants.create(tenant_name, tenant_name)
            tenant = self.driver.shell.auth_manager.tenants.find(name=tenant_name)
        else:
            tenant = tenants[0]
        return tenant
            

    def create_instance_key(self, slice_hrn, user):
        slice_name = Xrn(slice_hrn).leaf
        user_name = Xrn(user['urn']).leaf
        key_name = "%s_%s" % (slice_name, user_name)
        pubkey = user['keys'][0]
        key_found = False
        existing_keys = self.driver.shell.nova_manager.keypairs.findall(name=key_name)
        for existing_key in existing_keys:
            if existing_key.public_key != pubkey:
                self.driver.shell.nova_manager.keypairs.delete(existing_key)
            elif existing_key.public_key == pubkey:
                key_found = True

        if not key_found:
            self.driver.shell.nova_manager.keypairs.create(key_name, pubkey)
        return key_name       
        

    def create_security_group(self, slicename, fw_rules=[]):
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

 

    def run_instances(self, instance_name, tenant_name, rspec, key_name, pubkeys):
        #logger.debug('Reserving an instance: image: %s, flavor: ' \
        #            '%s, key: %s, name: %s' % \
        #            (image_id, flavor_id, key_name, slicename))

        # make sure a tenant exists for this slice
        tenant = self.create_tenant(tenant_name)  

        # add the sfa admin user to this tenant and update our nova client connection
        # to use these credentials for the rest of this session. This emsures that the instances
        # we create will be assigned to the correct tenant.
        sfa_admin_user = self.driver.shell.auth_manager.users.find(name=self.driver.shell.auth_manager.opts['OS_USERNAME'])
        user_role = self.driver.shell.auth_manager.roles.find(name='user')
        admin_role = self.driver.shell.auth_manager.roles.find(name='admin')
        self.driver.shell.auth_manager.roles.add_user_role(sfa_admin_user, admin_role, tenant)
        self.driver.shell.auth_manager.roles.add_user_role(sfa_admin_user, user_role, tenant)
        self.driver.shell.nova_manager.connect(tenant=tenant.name)  

        authorized_keys = "\n".join(pubkeys)
        files = {'/root/.ssh/authorized_keys': authorized_keys}
        rspec = RSpec(rspec)
        requested_instances = defaultdict(list)
        # iterate over clouds/zones/nodes
        for node in rspec.version.get_nodes_with_slivers():
            instances = node.get('slivers', [])
            if not instances:
                continue
            for instance in instances:
                try: 
                    metadata = {}
                    flavor_id = self.driver.shell.nova_manager.flavors.find(name=instance['name'])
                    image = instance.get('disk_image')
                    if image and isinstance(image, list):
                        image = image[0]
                    else:
                        raise InvalidRSpec("Must specify a disk_image for each VM")
                    image_id = self.driver.shell.nova_manager.images.find(name=image['name'])
                    fw_rules = instance.get('fw_rules', [])
                    group_name = self.create_security_group(instance_name, fw_rules)
                    metadata['security_groups'] = group_name
                    if node.get('component_id'):
                        metadata['component_id'] = node['component_id']
                    if node.get('client_id'):
                        metadata['client_id'] = node['client_id']
                    self.driver.shell.nova_manager.servers.create(flavor=flavor_id,
                                                            image=image_id,
                                                            key_name = key_name,
                                                            security_groups = [group_name],
                                                            files=files,
                                                            meta=metadata, 
                                                            name=instance_name)
                except Exception, err:    
                    logger.log_exc(err)                                
                           


    def delete_instances(self, instance_name, tenant_name):

        def _delete_security_group(instance):
            security_group = instance.metadata.get('security_groups', '')
            if security_group:
                manager = SecurityGroup(self.driver)
                timeout = 10.0 # wait a maximum of 10 seconds before forcing the security group delete
                start_time = time.time()
                instance_deleted = False
                while instance_deleted == False and (time.time() - start_time) < timeout:
                    inst = self.driver.shell.nova_manager.servers.findall(id=instance.id)
                    if not inst:
                        instance_deleted = True
                    time.sleep(.5)
                manager.delete_security_group(security_group)

        thread_manager = ThreadManager()
        self.driver.shell.nova_manager.connect(tenant=tenant_name)
        instances = self.driver.shell.nova_manager.servers.findall(name=instance_name)
        for instance in instances:
            # destroy instance
            self.driver.shell.nova_manager.servers.delete(instance)
            # deleate this instance's security groups
            thread_manager.run(_delete_security_group, instance)
        return 1


    def stop_instances(self, instance_name, tenant_name):
        self.driver.shell.nova_manager.connect(tenant=tenant_name)
        instances = self.driver.shell.nova_manager.servers.findall(name=instance_name)
        for instance in instances:
            self.driver.shell.nova_manager.servers.pause(instance)
        return 1

    def update_instances(self, project_name):
        pass
