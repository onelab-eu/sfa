from sfa.generic import Generic
import sfa.plc.plcsfaapi

class pl (Generic):
    
    def api_class (self):
        return sfa.plc.plcsfaapi.PlcSfaApi


