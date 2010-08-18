### $Id$
### $URL$

from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.Remove import Remove

class remove(Remove):
    """
    Deprecated. Use Remove instead.

    Remove an object from the registry. If the object represents a PLC object,
    then the PLC records will also be removed.
    
    @param cred credential string
    @param type record type
    @param xrn human readable name of record to remove (hrn or urn)

    @return 1 if successful, faults otherwise 
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(str, "Record type"),
        Parameter(str, "Human readable name of slice to instantiate (hrn or urn)"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, cred, type, xrn, origin_hrn=None):
        
        return Remove.call(self, xrn, cred, type) 
