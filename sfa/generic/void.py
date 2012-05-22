# This setting is designed for running a registry-only SFA instance

from sfa.generic import Generic

class void (Generic):
    
    # the importer class
    def importer_class (self): 
        import sfa.importer.plimporter
        return sfa.importer.Importer
        
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
    # most likely you'll want to turn OFF the aggregate in sfa-config-tty
    # SFA_AGGREGATE_ENABLED=false
    def aggregate_manager_class (self) :
        import sfa.managers.aggregate_manager
        return sfa.managers.aggregate_manager.AggregateManager

    # driver class for server-side services, talk to the whole testbed
    def driver_class (self):
        import sfa.managers
        return sfa.managers.driver

