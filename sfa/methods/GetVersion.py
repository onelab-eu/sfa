from sfa.util.method import Method

from sfa.storage.parameter import Parameter


class GetVersion(Method):
    """
    Returns this GENI Aggregate Manager's Version Information
    @return version
    """
    interfaces = ['registry','aggregate', 'slicemgr', 'component']
    accepts = []
    returns = Parameter(dict, "Version information")

    def call(self):
        self.api.logger.info("interface: %s\tmethod-name: %s" % (self.api.interface, self.name))
        return self.api.manager.GetVersion(self.api)
