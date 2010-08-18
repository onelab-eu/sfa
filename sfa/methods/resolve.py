### $Id$
### $URL$
import traceback
import types
from sfa.util.faults import *
from sfa.util.namespace import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.record import SfaRecord
from sfa.methods.Resolve import Resolve

class resolve(Resolve):
    """
    Deprecated. Use Resolve instead
    Resolve a record.

    @param cred credential string authorizing the caller
    @param hrn human readable name to resolve (hrn or urn) 
    @return a list of record dictionaries or empty list     
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Mixed(Parameter(str, "Human readable name (hrn or urn)"),
              Parameter(list, "List of Human readable names ([hrn])"))  
        ]

    returns = [SfaRecord]
    
    def call(self, cred, xrns, origin_hrn=None):
        return Resolve.call(self, xrns, cred)


            
