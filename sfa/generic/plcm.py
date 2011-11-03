from sfa.generic.pl import pl
import sfa.plc.plccomponentapi
import sfa.managers.component_manager_pl

class plcm (pl):

    def api_class (self):
        return sfa.plc.plccomponentapi.PlcComponentApi

    def component_class (self):
        return sfa.managers.component_manager_pl
