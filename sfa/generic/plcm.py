from sfa.generic.pl import pl

import sfa.server.sfaapi
import sfa.plc.plccomponentapi
import sfa.managers.component_manager_pl

class plcm (pl):

    def component_class (self):
        return sfa.managers.component_manager_pl

    def driver_class (self):
        return 'xxx todo : transform plccomponentapi into plcnodedriver'
