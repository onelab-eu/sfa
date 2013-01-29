from sfa.generic import Generic

class teagle (Generic):
    
    # the importer class
    def importer_class (self): 
        import sfa.importer.dummyimporter
        return sfa.importer.dummyimporter.DummyImporter
        
    # use the standard api class
    def api_class (self):
        import sfa.server.sfaapi
        return sfa.server.sfaapi.SfaApi

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
        import teaglesfa.driver
        return teaglesfa.driver.TeagleDriver
#        import sfa.dummy.dummydriver
#        return sfa.dummy.dummydriver.DummyDriver

