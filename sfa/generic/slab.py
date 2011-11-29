from sfa.generic import Generic

import sfa.server.sfaapi
import sfa.senslab.slabdriver
import sfa.managers.registry_manager_slab
import sfa.managers.slice_manager
import sfa.managers.aggregate_manager_slab

class slab (Generic):
    
    # use the standard api class
    def api_class (self):
        return sfa.server.sfaapi.SfaApi

    # the manager classes for the server-side services
    def registry_manager_class (self) : 
        return sfa.managers.registry_manager_slab
    def slicemgr_manager_class (self) : 
        return sfa.managers.slice_manager.SliceManager
    def aggregate_manager_class (self) :
        return sfa.managers.aggregate_manager_slab.AggregateManager

    # driver class for server-side services, talk to the whole testbed
    def driver_class (self):
        return sfa.senslab.slabdriver.SlabDriver

    # slab does not have a component manager yet
    # manager class
    def component_manager_class (self):
        return None
    # driver_class
    def component_driver_class (self):
        return None


