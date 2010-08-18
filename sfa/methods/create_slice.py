### $Id$
### $URL$

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.CreateSliver import CreateSliver

class create_slice(CreateSliver):
    """
    Deprecated. Use CreateSliver instead.
    Instantiate the specified slice according to whats defined in the specified rspec      

    @param cred credential string specifying the rights of the caller
    @param hrn human readable name of slice to instantiate (hrn or xrn)
    @param rspec resource specification
    @return 1 is successful, faults otherwise  
    """

    interfaces = ['aggregate', 'slicemgr']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(str, "Human readable name of slice to instantiate (hrn or xrn)"),
        Parameter(str, "Resource specification"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
        
    def call(self, cred, xrn, requested_rspec, origin_hrn=None):

        return CreateSliver.call(self, xrn, cred, requested_rspec, []) 
