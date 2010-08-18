### $Id$
### $URL$

from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.ListSlices import ListSlices

class get_slices(ListSlices):
    """
    Deprecated. Use ListSlices instead.
    Get a list of instantiated slices at this authority.      

    @param cred credential string specifying the rights of the caller
    @return list of human readable slice names (hrn).  
    """

    interfaces = ['aggregate', 'slicemgr', 'component']
    
    accepts = [
        Parameter(str, "Credential string"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = [Parameter(str, "Human readable slice name (hrn)")]
    
    def call(self, cred, origin_hrn=None):

        return ListSlices.call(self, cred)
