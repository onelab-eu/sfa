# 
from sfa.generic.pl import pl

import sfa.federica.fddriver

# the federica flavour behaves like pl, except for 
# the driver

class fd (pl):

    def driver_class (self) :
        import sfa.managers.v2_to_v3_adapter
        return sfa.managers.v2_to_v3_adapter.V2ToV3Adapter
