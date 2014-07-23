import datetime

from sfa.util.faults import InsufficientRights
from sfa.util.xrn import urn_to_hrn
from sfa.util.method import Method
from sfa.util.sfatime import utcparse, add_datetime

from sfa.trust.credential import Credential

from sfa.storage.parameter import Parameter

class Renew(Method):
    """
    Renews the resources in the specified slice or slivers by 
    extending the lifetime.
    
    @param urns ([string]) List of URNs of to renew
    @param credentials ([string]) of credentials
    @param expiration_time (string) requested time of expiration
    @param options (dict) options
    """
    interfaces = ['aggregate', 'slicemgr']
    accepts = [
        Parameter(type([str]), "Slice URN"),
        Parameter(type([str]), "List of credentials"),
        Parameter(str, "Expiration time in RFC 3339 format"),
        Parameter(dict, "Options"),
        ]
    returns = Parameter(bool, "Success or Failure")

    def call(self, urns, creds, expiration_time, options):


        # Find the valid credentials
        valid_creds = self.api.auth.checkCredentialsSpeaksFor(creds, 'renewsliver', urns,
                                                              check_sliver_callback = self.api.driver.check_sliver_credentials,
                                                              options=options)
        the_credential = Credential(cred=valid_creds[0])
        actual_caller_hrn = the_credential.actual_caller_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-urns: %s\texpiration:%s\tmethod-name: %s"%\
                             (self.api.interface, actual_caller_hrn, urns, expiration_time,self.name))


        # extend as long as possible : take the min of requested and now+SFA_MAX_SLICE_RENEW
        if options.get('geni_extend_alap'):
            # ignore requested time and set to max
            expiration_time = add_datetime(datetime.datetime.utcnow(), days=int(self.api.config.SFA_MAX_SLICE_RENEW))

        # Validate that the time does not go beyond the credential's expiration time
        requested_expire = utcparse(expiration_time)
        self.api.logger.info("requested_expire = %s"%requested_expire)
        credential_expire = the_credential.get_expiration()
        self.api.logger.info("credential_expire = %s"%credential_expire)
        max_renew_days = int(self.api.config.SFA_MAX_SLICE_RENEW)
        max_expire = datetime.datetime.utcnow() + datetime.timedelta (days=max_renew_days)
        if requested_expire > credential_expire:
            # used to throw an InsufficientRights exception here, this was not right
            self.api.logger.warning("Requested expiration %s, after credential expiration (%s) -> trimming to the latter/sooner"%\
                                    (requested_expire, credential_expire))
            requested_expire = credential_expire
        if requested_expire > max_expire:
            # likewise
            self.api.logger.warning("Requested expiration %s, after maximal expiration %s days (%s) -> trimming to the latter/sooner"%\
                                    (requested_expire, self.api.config.SFA_MAX_SLICE_RENEW,max_expire))
            requested_expire = max_expire

        return self.api.manager.Renew(self.api, urns, creds, requested_expire, options)
    
