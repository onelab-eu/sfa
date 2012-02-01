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

    def instance_to_sliver(instance, slice_xrn=None):
        sliver_id = None
        if slice_xrn:
            xrn = OSXrn(slice_xrn, 'slice')
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
                         'name': xrn.name,
                         'type': 'plos-' + instance.name,
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
        return slivers

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
