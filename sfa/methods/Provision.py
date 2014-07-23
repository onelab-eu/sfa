from sfa.util.faults import SfaInvalidArgument, InvalidRSpec
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatablesRuntime import run_sfatables
from sfa.trust.credential import Credential
from sfa.storage.parameter import Parameter, Mixed
from sfa.rspecs.rspec import RSpec

class Provision(Method):
    """
    Request that the named geni_allocated slivers be made 
    geni_provisioned, instantiating or otherwise realizing the 
    resources, such that they have a valid geni_operational_status 
    and may possibly be made geni_ready for experimenter use. This 
    operation is synchronous, but may start a longer process, such 
    as creating and imaging a virtual machine

    @param slice urns ([string]) URNs of slivers to provision to
    @param credentials (dict) of credentials
    @param options (dict) options
    
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(type([str]), "URNs"),
        Parameter(type([dict]), "Credentials"),
        Parameter(dict, "options"),
        ]
    returns = Parameter(dict, "Provisioned Resources")

    def call(self, xrns, creds, options):
        self.api.logger.info("interface: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, xrns, self.name))

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentialsSpeaksFor(creds, 'createsliver', xrns,
                                                              check_sliver_callback = self.api.driver.check_sliver_credentials,
                                                              options=options)
        origin_hrn = Credential(cred=valid_creds[0]).get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, xrns, self.name))
        result = self.api.manager.Provision(self.api, xrns, creds, options)
        return result
