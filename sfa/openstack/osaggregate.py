import base64

from nova.exception import ImageNotFound
from nova.api.ec2.cloud import CloudController
from sfa.util.faults import SfaAPIError
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.disk_image import DiskImage
from sfa.rspecs.elements.services import Services
from sfa.util.xrn import Xrn
from sfa.util.osxrn import OSXrn
from sfa.rspecs.version_manager import VersionManager
from sfa.openstack.image import Image
from sfa.openstack.security_group import SecurityGroup


def instance_to_sliver(instance, slice_xrn=None):
    # should include?
    # * instance.image_ref
    # * instance.kernel_id
    # * instance.ramdisk_id
    import nova.db.sqlalchemy.models
    name=None
    type=None
    sliver_id = None
    if isinstance(instance, dict):
        # this is an isntance type dict
        name = instance['name']
        type = instance['name']
    elif isinstance(instance, nova.db.sqlalchemy.models.Instance):
        # this is an object that describes a running instance
        name = instance.display_name
        type = instance.instance_type.name
    else:
        raise SfaAPIError("instnace must be an instance_type dict or" + \
                           " a nova.db.sqlalchemy.models.Instance object")
    if slice_xrn:
        xrn = Xrn(slice_xrn, 'slice')
        sliver_id = xrn.get_sliver_id(instance.project_id, instance.hostname, instance.id)

    sliver = Sliver({'slice_id': sliver_id,
                     'name': name,
                     'type': 'plos-' + type,
                     'tags': []})
    return sliver
            

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

    def get_slice_nodes(self, slice_xrn):
        image_manager = Image(self.driver)
        name = OSXrn(xrn = slice_xrn).name
        instances = self.driver.shell.db.instance_get_all_by_project(name)
        rspec_nodes = []
        for instance in instances:
            rspec_node = Node()
            xrn = OSXrn(instance.hostname, 'node')
            rspec_node['component_id'] = xrn.urn
            rspec_node['component_name'] = xrn.name
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()   
            sliver = instance_to_sliver(instance)
            disk_image = image_manager.get_disk_image(instance.image_ref)
            sliver['disk_images'] = [Image.disk_image_to_rspec_object(disk_image)]
            rspec_node['slivers'] = [sliver]
            rspec_nodes.append(rspec_node)
        return rspec_nodes

    def get_aggregate_nodes(self):
                
        zones = self.driver.shell.db.zone_get_all()
        if not zones:
            zones = ['cloud']
        else:
            zones = [zone.name for zone in zones]

        # available sliver/instance/vm types
        instances = self.driver.shell.db.instance_type_get_all().values()
        # available images
        image_manager = Image(self.driver)
        disk_images = image_manager.get_available_disk_images()
        disk_image_objects = [Image.disk_image_to_rspec_object(image) \
                               for image in disk_images]  
        rspec_nodes = []
        for zone in zones:
            rspec_node = Node()
            xrn = OSXrn(zone, 'node')
            rspec_node['component_id'] = xrn.urn
            rspec_node['component_name'] = xrn.name
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()
            rspec_node['exclusive'] = 'false'
            rspec_node['hardware_types'] = [HardwareType({'name': 'plos-pc'}),
                                                HardwareType({'name': 'pc'})]
            slivers = []
            for instance in instances:
                sliver = instance_to_sliver(instance)
                sliver['disk_images'] = disk_image_objects
                slivers.append(sliver)
        
            rspec_node['slivers'] = slivers
            rspec_nodes.append(rspec_node) 

        return rspec_nodes 


    def create_project(self, slicename, users, options={}):
        """
        Create the slice if it doesn't alredy exist. Create user
        accounts that don't already exist   
        """
        import nova.exception.ProjectNotFound
        try:
            slice = self.driver.shell.auth_manager.get_project(slicename)
        except nova.exception.ProjectNotFound:
            # assume that the first user is the project manager
            proj_manager = Xrn(users[0]['urn']).get_leaf() 
            self.driver.shell.auth_manager.create_project(slicename, proj_manager)
           
        for user in users:
            username = Xrn(user['urn']).get_leaf()
            try:
                self.driver.shell.auth_manager.get_user(username)
            except nova.exception.UserNotFound:
                self.driver.shell.auth_manager.create_user(username)
            self.verify_user_keys(username, user['keys'], options) 

    def verify_user_keys(self, username, keys, options={}):
        """
        Add requested keys.
        """
        append = options.get('append', True)    
        existing_keys = self.driver.shell.db.key_pair_get_all_by_user(username)
        existing_pub_keys = [key.public_key for key in existing_keys]
        removed_pub_keys = set(existing_pub_keys).difference(keys)
        added_pub_keys = set(keys).difference(existing_pub_keys)
        pubkeys = []
        # add new keys
        for public_key in added_pub_keys:
            key = {}
            key['user_id'] = username
            key['name'] =  username
            key['public'] = public_key
            self.driver.shell.db.key_pair_create(key)

        # remove old keys
        if not append:
            for key in existing_keys:
                if key.public_key in removed_pub_keys:
                    self.driver.shell.db.key_pair_destroy(username, key.name)


    def create_security_group(self, group_name, fw_rules=[]):
        security_group = SecurityGroup(self.driver)
        security_group.create_security_group(group_name)
        for rule in fw_rules:
            security_group.add_rule_to_group(group_name, 
                                             protocol = rule.get('protocol'), 
                                             cidr_ip = rule.get('cidr_ip'), 
                                             port_range = rule.get('port_range'), 
                                             icmp_type_code = rule.get('icmp_type_code'))

    def add_rule_to_security_group(self, group_name, **kwds):
        security_group = SecurityGroup(self.driver)
        security_group.add_rule_to_group(group_name=group_name, 
                                         protocol=kwds.get('protocol'), 
                                         cidr_ip =kwds.get('cidr_ip'), 
                                         icmp_type_code = kwds.get('icmp_type_code'))

 
    def reserve_instance(self, image_id, kernel_id, ramdisk_id, \
                         instance_type, key_name, user_data):
        conn  = self.driver.euca_shell
        logger.info('Reserving an instance: image: %s, kernel: ' + \
                    '%s, ramdisk: %s, type: %s, key: %s' % \
                    (image_id, kernel_id, ramdisk_id,
                    instance_type, key_name))
        try:
            reservation = conn.run_instances(image_id=image_id,
                                             kernel_id=kernel_id,
                                             ramdisk_id=ramdisk_id,
                                             instance_type=instance_type,
                                             key_name=key_name,
                                             user_data = user_data,
                                             security_groups=group_names)
                                             #placement=zone,
                                             #min_count=min_count,
                                             #max_count=max_count,           
                                              
        except EC2ResponseError, ec2RespError:
            logger.log_exc(ec2RespError)
               
    def run_instances(self, slicename, rspec, keyname, pubkeys):
        """
        Create the security groups and instances. 
        """
        # the default image to use for instnaces that dont
        # explicitly request an image.
        # Just choose the first available image for now.
        image_manager = Image(self.driver)
        available_images = image_manager.get_available_disk_images()
        default_image = image_manager.get_disk_images()[0]    
        default_ami_id = CloudController.image_ec2_id(default_image['ami']['id'])  
        default_aki_id = CloudController.image_ec2_id(default_image['aki']['id'])  
        default_ari_id = CloudController.image_ec2_id(default_image['ari']['id'])

        # get requested slivers
        rspec = RSpec(rspec)
        requested_instances = defaultdict(list)
        # iterate over clouds/zones/nodes
        for node in rspec.version.get_nodes_with_slivers():
            instance_types = node.get('slivers', [])
            if isinstance(instance_types, list):
                # iterate over sliver/instance types
                for instance_type in instance_types:
                    fw_rules = instance_type.get('fw_rules', [])
                    # Each sliver get's its own security group.  
                    # Keep security group names unique by appending some random 
                    # characters on end.
                    group_name = "_".join([slicename, 
                                           instance_type['name'],
                                           base64.b64encode(os.urandom(6))])  
                    self.create_security_group(group_name, fw_rules)
                    ami_id = default_ami_id
                    aki_id = default_aki_id
                    ari_id = default_ari_id
                    req_image = instance_type.get('disk_images')
                    if req_image and isinstance(req_image, list):
                        req_image_name = req_image[0]['name']
                        disk_image = image_manager.get_disk_image(name=req_image_name)
                        if disk_image:
                            ami_id = CloudController.image_ec2_id(disk_image['ami']['id'])
                            aki_id = CloudController.image_ec2_id(disk_image['aki']['id'])
                            ari_id = CloudController.image_ec2_id(disk_image['ari']['id'])
                    # start the instance
                    self.reserve_instance(image_id=ami_id, 
                                          kernel_id=aki_id, 
                                          ramdisk_id=ari_id, 
                                          instance_type=instance_type['name'], 
                                          key_name=keyname, 
                                          user_data=pubkeys, 
                                          group_name=group_name)


    def delete_instances(self, project_name):
        instances = self.driver.shell.db.instance_get_all_by_project(project_name)
        security_group_manager = SecurityGroup(self)
        for instance in instances:
            # deleate this instance's security groups
            for security_group in instance.security_groups:
                # dont delete the default security group
                if security_group.name != 'default': 
                    security_group_manager.delete_security_group(security_group.name)
            # destroy instance
            self.driver.shell.db.instance_destroy(instance.id)
        return 1

    def stop_instances(self, project_name):
        instances = self.driver.shell.db.instance_get_all_by_project(project_name)
        for instance in instances:
            self.driver.shell.db.instance_stop(instance.id)
        return 1

    def update_instances(self, project_name):
        pass
