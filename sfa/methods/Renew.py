import datetime

from sfa.util.faults import InsufficientRights
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatime import utcparse

from sfa.trust.credential import Credential

from sfa.storage.parameter import Parameter

class Renew(Method):
    """
    Renews the resources in the specified slice or slivers by 
    extending the lifetime.
    
    @param surn ([string]) List of URNs of to renew
    @param credentials ([string]) of credentials
    @param expiration_time (string) requested time of expiration
    @param options (dict) options
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(str, "Slice URN"),
        Parameter(type([str]), "List of credentials"),
        Parameter(str, "Expiration time in RFC 3339 format"),
        Parameter(dict, "Options"),
        ]
    returns = Parameter(bool, "Success or Failure")

    def call(self, urns, creds, expiration_time, options):

        self.api.logger.info("interface: %s\ttarget-hrn: %s\tcaller-creds: %s\tmethod-name: %s"%(self.api.interface, urns, creds, self.name))

        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentials(creds, 'renewsliver', urns)

        # Validate that the time does not go beyond the credential's expiration time
        requested_time = utcparse(expiration_time)
        max_renew_days = int(self.api.config.SFA_MAX_SLICE_RENEW)
        if requested_time > Credential(string=valid_creds[0]).get_expiration():
            raise InsufficientRights('Renewsliver: Credential expires before requested expiration time')
        if requested_time > datetime.datetime.utcnow() + datetime.timedelta(days=max_renew_days):
            raise Exception('Cannot renew > %s days from now' % max_renew_days)
        return self.api.manager.Renew(self.api, urns, creds, expiration_time, options)
    
