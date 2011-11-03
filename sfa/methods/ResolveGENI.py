from sfa.util.method import Method
from sfa.util.parameter import Parameter

class ResolveGENI(Method):
    """
    Lookup a URN and return information about the corresponding object.
    @param urn
    """

    interfaces = ['registry']
    accepts = [
        Parameter(str, "URN"),
        Parameter(type([str]), "List of credentials"),
        ]
    returns = Parameter(bool, "Success or Failure")

    def call(self, xrn):

        manager_base = 'sfa.managers'

        if self.api.interface in ['registry']:
            mgr_type = self.api.config.SFA_REGISTRY_TYPE
            manager_module = manager_base + ".registry_manager_%s" % mgr_type
            manager = __import__(manager_module, fromlist=[manager_base])
            return manager.Resolve(self.api, xrn, '')
               
        return {}
