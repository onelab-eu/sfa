# 
from sfa.generic.pl import pl

import sfa.federica.fddriver

class fd (pl):

# the max flavour behaves like pl, except for 
# the aggregate
    def driver_class (self) :
        return sfa.federica.fddriver.FdDriver
