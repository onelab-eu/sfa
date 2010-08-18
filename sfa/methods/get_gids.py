from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.methods.GetGids import GetGids

class get_gids(GetGids):
    """
    Deprecated. Use GetGids instead.

    Get a list of record information (hrn, gid and type) for 
    the specified hrns.

    @param cred credential string 
    @param cert certificate string 
    @return    
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Certificate string"),
        Mixed(Parameter(str, "Human readable name (hrn or xrn)"), 
              Parameter(type([str]), "List of Human readable names (hrn or xrn)")) 
        ]

    returns = [Parameter(dict, "Dictionary of gids keyed on hrn")]
    
    def call(self, cred, xrns):
        
        return GetGids.call(self, xrns, cred)     
