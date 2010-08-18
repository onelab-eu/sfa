### $Id$
### $URL$
import time
from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.GetTicket import GetTicket

class get_ticket(GetTicket):
    """
    Deprecated. Use GetTicket instead.

    Retrieve a ticket. This operation is currently implemented on PLC
    only (see SFA, engineering decisions); it is not implemented on
    components.
    
    The ticket is filled in with information from the PLC database. This
    information includes resources, and attributes such as user keys and
    initscripts.
    
    @param cred credential string
    @param name name of the slice to retrieve a ticket for (hrn or urn)
    @param rspec resource specification dictionary
    
    @return the string representation of a ticket object
    """

    interfaces = ['aggregate', 'slicemgr']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(str, "Human readable name of slice to retrive a ticket for (hrn or urn)"),
        Parameter(str, "Resource specification (rspec)"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(str, "String represeneation of a ticket object")
    
    def call(self, cred, xrn, rspec, origin_hrn=None):
        
        return GetTicket.call(self, xrn, cred, rspec, None)        
