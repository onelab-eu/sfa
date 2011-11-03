from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.server.registry import Registries

class get_registries(Method):
    """
    Get a list of connection information for all known registries.      

    @param cred credential string specifying the rights of the caller
    @param a Human readable name (hrn or urn), or list of names or None
    @return list of dictionaries with aggregate information.  
    """

    interfaces = ['registry', 'aggregate', 'slicemgr']
    
    accepts = [
        Parameter(str, "Credential string"),
        Mixed(Parameter(str, "Human readable name (hrn or urn)"),
              Parameter(None, "hrn not specified"))
        ]

    returns = [Parameter(dict, "Registry interface information")]
    
    def call(self, cred, xrn = None):
        hrn, type = urn_to_hrn(xrn)
        self.api.auth.check(cred, 'list')
        registries = Registries(self.api).values()
        if hrn:
            registries = [reg for reg in registries if reg['hrn'] == hrn] 
        return registries
