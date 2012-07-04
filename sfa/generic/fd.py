# 
from sfa.generic.pl import pl

import sfa.federica.fddriver

# the federica flavour behaves like pl, except for 
# the driver

class fd (pl):

    def driver_class (self) :
        return sfa.federica.fddriver.FdDriver
