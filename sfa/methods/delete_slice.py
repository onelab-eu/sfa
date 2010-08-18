### $Id$
### $URL$

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.DeleteSliver import DeleteSliver

class delete_slice(DeleteSliver):
    """
    Deprecated. Use delete instead.

    Remove the slice from all nodes.      

    @param cred credential string specifying the rights of the caller
    @param xrn human readable name specifying the slice to delete (hrn or urn)
    @return 1 if successful, faults otherwise  
    """

    interfaces = ['aggregate', 'slicemgr', 'component']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(str, "Human readable name of slice to delete (hrn or urn)"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, cred, xrn, origin_hrn=None):

        return DeleteSliver.call(self, xrn, cred)
