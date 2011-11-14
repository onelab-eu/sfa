from sfa.generic import Generic

import sfa.server.sfaapi
import sfa.plc.pldriver
import sfa.managers.registry_manager
import sfa.managers.slice_manager
import sfa.managers.aggregate_manager

class pl (Generic):
    
    # use the standard api class
    def api_class (self):
        return sfa.server.sfaapi.SfaApi

    # the manager classes for the server-side services
    def registry_manager_class (self) : 
        return sfa.managers.registry_manager.RegistryManager
    def slicemgr_manager_class (self) : 
        return sfa.managers.slice_manager.SliceManager
    def aggregate_manager_class (self) :
        return sfa.managers.aggregate_manager.AggregateManager

    # driver class for server-side services, talk to the whole testbed
    def driver_class (self):
        return sfa.plc.pldriver.PlDriver

    # for the component mode, to be run on board planetlab nodes
    # manager class
    def component_manager_class (self):
        return sfa.managers.component_manager_pl
    # driver_class
    def component_driver_class (self):
        return sfa.plc.plcomponentdriver.PlComponentDriver


