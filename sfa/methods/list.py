### $Id$
### $URL$

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.record import SfaRecord
from sfa.methods.List import List

class list(List):
    """
    Deprecated. Use List instead.

    List the records in an authority. 

    @param cred credential string specifying the rights of the caller
    @param hrn human readable name of authority to list (hrn or urn)
    @return list of record dictionaries         
    """
    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(str, "Human readable name (hrn or urn)"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = [SfaRecord]
    
    def call(self, cred, xrn, origin_hrn=None):
        
        return List.call(self, xrn, cred) 
