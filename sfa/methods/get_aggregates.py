from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.server.aggregate import Aggregates

class get_aggregates(Method):
    """
    Get a list of connection information for all known aggregates.      

    @param cred credential string specifying the rights of the caller
    @param a Human readable name (hrn or urn), or list of hrns or None
    @return list of dictionaries with aggregate information.  
    """

    interfaces = ['registry', 'aggregate', 'slicemgr']
    
    accepts = [
        Parameter(str, "Credential string"),
        Mixed(Parameter(str, "Human readable name (hrn or urn)"),
              Parameter(None, "hrn not specified"))
        ]

    returns = [Parameter(dict, "Aggregate interface information")]
    
    def call(self, cred, xrn = None):
        hrn, type = urn_to_hrn(xrn)
        self.api.auth.check(cred, 'list')
        aggregates = Aggregates(self.api).interfaces.values()
        if hrn:
            aggregates = [agg for agg in aggregates if agg['hrn'] == hrn]
        return aggregates
