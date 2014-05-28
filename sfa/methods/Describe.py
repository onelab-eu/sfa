import zlib

from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatablesRuntime import run_sfatables
from sfa.util.faults import SfaInvalidArgument
from sfa.trust.credential import Credential

from sfa.storage.parameter import Parameter, Mixed

class Describe(Method):
    """
    Retrieve a manifest RSpec describing the resources contained by the 
    named entities, e.g. a single slice or a set of the slivers in a 
    slice. This listing and description should be sufficiently 
    descriptive to allow experimenters to use the resources.    
    @param credential list
    @param options dictionary
    @return dict
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(type([str]), "List of URNs"),
        Mixed(Parameter(str, "Credential string"), 
              Parameter(type([str]), "List of credentials")),
        Parameter(dict, "Options")
        ]
    returns = Parameter(str, "List of resources")

    def call(self, urns, creds, options):
        self.api.logger.info("interface: %s\tmethod-name: %s" % (self.api.interface, self.name))
       
        # client must specify a version
        if not options.get('geni_rspec_version'):
            if options.get('rspec_version'):
                options['geni_rspec_version'] = options['rspec_version']
            else:
                raise SfaInvalidArgument('Must specify an rspec version option. geni_rspec_version cannot be null')
        valid_creds = self.api.auth.checkCredentialsSpeaksFor(creds, 'listnodes', urns, 
                                                              check_sliver_callback = self.api.driver.check_sliver_credentials,
                                                              options=options)

        # get hrn of the original caller 
        origin_hrn = options.get('origin_hrn', None)
        if not origin_hrn:
            origin_hrn = Credential(cred=valid_creds[0]).get_gid_caller().get_hrn()
        desc = self.api.manager.Describe(self.api, creds, urns, options)

        # filter rspec through sfatables 
        if self.api.interface in ['aggregate']:
            chain_name = 'OUTGOING'
        elif self.api.interface in ['slicemgr']: 
            chain_name = 'FORWARD-OUTGOING'
        self.api.logger.debug("ListResources: sfatables on chain %s"%chain_name)
        desc['geni_rspec'] = run_sfatables(chain_name, '', origin_hrn, desc['geni_rspec']) 
 
        if options.has_key('geni_compressed') and options['geni_compressed'] == True:
            desc['geni_rspec'] = zlib.compress(desc['geni_rspec']).encode('base64')

        return desc  
    
    
