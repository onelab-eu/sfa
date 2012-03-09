from sfa.generic import Generic

import sfa.server.sfaapi



class slab (Generic):
    
    # use the standard api class
    def api_class (self):
        return sfa.server.sfaapi.SfaApi
    
    # the importer class
    def importer_class (self): 
        import sfa.importer.slabimporter
        return sfa.importer.slabimporter.SlabImporter
    
    # the manager classes for the server-side services
    def registry_manager_class (self) :
        import sfa.managers.registry_manager 
        return sfa.managers.registry_manager.RegistryManager
    
    def slicemgr_manager_class (self) :
        import sfa.managers.slice_manager 
        return sfa.managers.slice_manager.SliceManager
    
    def aggregate_manager_class (self) :
        import sfa.managers.aggregate_manager
        return sfa.managers.aggregate_manager.AggregateManager

    # driver class for server-side services, talk to the whole testbed
    def driver_class (self):
        import sfa.senslab.slabdriver
        return sfa.senslab.slabdriver.SlabDriver

    # slab does not have a component manager yet
    # manager class
    def component_manager_class (self):
        return None
    # driver_class
    def component_driver_class (self):
        return None


