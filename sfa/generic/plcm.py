from sfa.generic.pl import pl
import sfa.plc.plccomponentapi

class plcm (pl):

    def api_class (self):
        return sfa.plc.plccomponentapi.PlcComponentApi

