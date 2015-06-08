from sfa.generic import Generic

class openstack (Generic):
    
    # the importer class
    def importer_class (self): 
        import sfa.importer.openstackimporter
        return sfa.importer.openstackimporter.OpenstackImporter
    
    # use the standard api class
    def api_class (self):
       import sfa.server.sfaapi
       return sfa.server.sfaapi.SfaApi

    # the manager classes for the server-side services
    def registry_manager_class (self) : 
        import sfa.managers.registry_manager_openstack
        return sfa.managers.registry_manager_openstack.RegistryManager
    def slicemgr_manager_class (self) :
        import sfa.managers.slice_manager
        return sfa.managers.slice_manager.SliceManager
    def aggregate_manager_class (self) :
        import sfa.managers.aggregate_manager
        return sfa.managers.aggregate_manager.AggregateManager

    # driver class for server-side services, talk to the whole testbed
    def driver_class (self):
        import sfa.openstack.osdriver
        return sfa.openstack.osdriver.OpenstackDriver

    # for the component mode, to be run on board KOREN nodes
    # manager class
    def component_manager_class (self):
        # import sfa.managers
        # return sfa.managers.component_manager_default
        return None
    # driver_class
    def component_driver_class (self):
        #import sfa.planetlab.plcomponentdriver
        #return sfa.planetlab.plcomponentdriver.PlComponentDriver
        return None
