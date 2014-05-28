import zlib

from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatablesRuntime import run_sfatables
from sfa.util.faults import SfaInvalidArgument
from sfa.trust.credential import Credential

from sfa.storage.parameter import Parameter, Mixed

class ListResources(Method):
    """
    Returns information about available resources
    @param credential list
    @param options dictionary
    @return string
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Mixed(Parameter(str, "Credential string"), 
              Parameter(type([str]), "List of credentials")),
        Parameter(dict, "Options")
        ]
    returns = Parameter(str, "List of resources")

    def call(self, creds, options):
        self.api.logger.info("interface: %s\tmethod-name: %s" % (self.api.interface, self.name))
       
        # client must specify a version
        if not options.get('geni_rspec_version'):
            if options.get('rspec_version'):
                options['geni_rspec_version'] = options['rspec_version']
            else:
                raise SfaInvalidArgument('Must specify an rspec version option. geni_rspec_version cannot be null')

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentialsSpeaksFor(creds, 'listnodes', options=options)

        # get hrn of the original caller 
        origin_hrn = options.get('origin_hrn', None)
        if not origin_hrn:
            origin_hrn = Credential(cred=valid_creds[0]).get_gid_caller().get_hrn()
        rspec = self.api.manager.ListResources(self.api, creds, options)

        # filter rspec through sfatables 
        if self.api.interface in ['aggregate']:
            chain_name = 'OUTGOING'
        elif self.api.interface in ['slicemgr']: 
            chain_name = 'FORWARD-OUTGOING'
        self.api.logger.debug("ListResources: sfatables on chain %s"%chain_name)
        filtered_rspec = run_sfatables(chain_name, '', origin_hrn, rspec) 
 
        if options.has_key('geni_compressed') and options['geni_compressed'] == True:
            filtered_rspec = zlib.compress(filtered_rspec).encode('base64')

        return filtered_rspec  
    
    
