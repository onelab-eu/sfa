from sfa.generic import Generic
import sfa.plc.plcsfaapi
import sfa.managers.registry_manager
import sfa.managers.slice_manager
import sfa.managers.aggregate_manager

class pl (Generic):
    
    def api_class (self):
        return sfa.plc.plcsfaapi.PlcSfaApi

    def registry_class (self) : 
        return sfa.managers.registry_manager
    def slicemgr_class (self) : 
        return sfa.managers.slice_manager
    def aggregate_class (self) :
        return sfa.managers.aggregate_manager


