from sfa.generic import Generic

import sfa.server.sfaapi
import sfa.openstack.nova_driver
import sfa.managers.registry_manager_openstack
import sfa.managers.aggregate_manager
import sfa.managers.slice_manager

class openstack (Generic):
    
    # use the standard api class
    def api_class (self):
        return sfa.server.sfaapi.SfaApi

    # the manager classes for the server-side services
    def registry_manager_class (self) : 
        return sfa.managers.registry_manager_openstack.RegistryManager
    def slicemgr_manager_class (self) : 
        return sfa.managers.slice_manager.SliceManager
    def aggregate_manager_class (self) :
        return sfa.managers.aggregate_manager.AggregateManager

    # driver class for server-side services, talk to the whole testbed
    def driver_class (self):
        return sfa.openstack.nova_driver.NovaDriver

    # for the component mode, to be run on board planetlab nodes
    # manager class
    def component_manager_class (self):
        return sfa.managers.component_manager_pl
    # driver_class
    def component_driver_class (self):
        return sfa.plc.plcomponentdriver.PlComponentDriver


