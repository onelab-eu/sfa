from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.node import Node
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.services import Services
from sfa.util.xrn import Xrn
from sfa.util.osxrn import OSXrn
from sfa.rspecs.version_manager import VersionManager

class OSAggregate:

    def __init__(self, driver):
        self.driver = driver

    def instance_to_sliver(self, instance, slice_xrn=None):
        sliver_id = None
        name = None
        if slice_xrn:
            name = OSXrn(slice_xrn, 'slice').name
            sliver_id = xrn.sliver_id(instance.instance_id, "")

        # should include: 
        # * instance.image_ref
        # * instance.kernel_id
        # * instance.ramdisk_id 
        name=None
        if hasattr(instance, 'name'):
            name = instance.name
        elif hasattr(instance, 'display_name'):
            name = instance.display_name 
        sliver = Sliver({'slice_id': sliver_id,
                         'name': name,
                         'type': 'plos-' + instance['name'],
                         'tags': []})
        return sliver

    def get_rspec(self, slice_xrn=None, vsersion=None, options={}):
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, version.version, 'ad')
            nodes = self.get_aggregate_nodes()
        else:
            rspec_version = version_manager._get_version(version.type, version.version, 'manifest')
            nodes = self.get_slice_nodes(slice_xrn)
        
        rspec.version.add_nodes(nodes)
        return rspec.toxml()

    def get_slice_nodes(self, slice_xrn):
        name = OSXrn(xrn = slice_xrn).name
        instances = self.driver.shell.instance_get_all_by_project(name)
        rspec_nodes = []
        for instance in instances:
            rspec_node = Node()
            xrn = OSXrn(instance.hostname, 'node')
            rspec_node['component_id'] = xrn.urn
            rspec_node['component_name'] = xrn.name
            rspec_node['component_manager_id'] = Xrn(self.driver.hrn, 'authority+cm').get_urn()   
            sliver = self.instance_to_sliver(instance) 
            rspec_node['slivers'] = [sliver]
            rspec_nodes.append(rspec_node)
        return rspec_nodes

    def get_aggregate_nodes(self):
                
        zones = self.driver.shell.zone_get_all()
        if not zones:
            zones = ['cloud']
        else:
            zones = [zone.name for zone in zones]

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
            instances = self.driver.shell.instance_type_get_all().values()
            slivers = [self.instance_to_sliver(inst) for inst in instances]
            rspec_node['slivers'] = slivers
            rspec_nodes.append(rspec_node) 

        return rspec_node 


    def verify_slice(self, slicename, users, options={}):
        """
        Create the slice if it doesn't alredy exist  
        """
        try:
            slice = self.driver.shell.auth_manager.get_project(slicename)
        except nova.exception.ProjectNotFound:
            # convert urns to user names
            usernames = [Xrn(user['urn']).get_leaf() for user in users]
            # assume that the first user is the project manager
            proj_manager = usernames[0] 
            self.driver.shell.auth_manager.create_project(slicename, proj_manager)

    def verify_slice_users(self, slicename, users, options={}):
        """
        Add requested users to the specified slice.  
        """
        
        # There doesn't seem to be an effcient way to 
        # look up all the users of a project, so lets not  
        # attempt to remove stale users . For now lets just
        # ensure that the specified users exist     
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
            
    def verify_instances(self, slicename, rspec):
        pass 
