### $Id$
### $URL$

from sfa.trust.certificate import Keypair, convert_public_key
from sfa.trust.gid import *
from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.Register import Register

class register(Register):
    """
    Deprecated. Used Register instead.

    Register an object with the registry. In addition to being stored in the
    SFA database, the appropriate records will also be created in the
    PLC databases
    
    @param cred credential string
    @param record_dict dictionary containing record fields
    
    @return gid string representation
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(dict, "Record dictionary containing record fields")
        ]

    returns = Parameter(int, "String representation of gid object")
    
    def call(self, cred, record, origin_hrn=None):
        
        return Register.call(self, record, cred)
