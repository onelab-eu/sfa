### $Id$
### $URL$

from sfa.trust.credential import *
from sfa.trust.rights import *
from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.GetCredential import GetCredential

class get_credential(GetCredential):
    """
    Deprecated. Use GetCredential instead.

    Retrive a credential for an object
    If cred == Nonee then the behavior reverts to get_self_credential

    @param cred credential object specifying rights of the caller
    @param type type of object (user | slice | sa | ma | node)
    @param hrn human readable name of object (hrn or urn)

    @return the string representation of a credential object  
    """

    interfaces = ['registry']
    
    accepts = [
        Mixed(Parameter(str, "credential"),
              Parameter(None, "No credential")),  
        Parameter(str, "Human readable name (hrn or urn)")
        ]

    returns = Parameter(str, "String representation of a credential object")

    def call(self, cred, type, xrn, origin_hrn=None):
        return GetCredential.call(self, cred, xrn, type)
