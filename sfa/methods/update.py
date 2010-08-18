### $Id$
### $URL$

import time
from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.Update import Update

class update(Update):
    """
    Deprecated. Use Update instead.

    Update an object in the registry. Currently, this only updates the
    PLC information associated with the record. The SFA fields (name, type,
    GID) are fixed.
    
    @param cred credential string specifying rights of the caller
    @param record a record dictionary to be updated

    @return 1 if successful, faults otherwise 
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(dict, "Record dictionary to be updated"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, cred, record_dict, origin_hrn=None):
        
        return Update.call(self, record_dict, cred)

