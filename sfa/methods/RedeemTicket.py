### $Id: reset_slice.py 15428 2009-10-23 15:28:03Z tmack $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfacomponent/methods/reset_slice.py $
import xmlrpclib
from sfa.util.faults import *
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed

class RedeemTicket(Method):
    """
    Deprecated. Use RedeemTicket instead.

    @param cred credential string specifying the rights of the caller
    @param ticket 
    @return 1 is successful, faults otherwise  
    """

    interfaces = ['component']
    
    accepts = [
        Parameter(str, "Ticket  string representation of SFA ticket"),
        Mixed(Parameter(str, "Credential string"),
              Parameter(type([str]), "List of credentials")),
        ]

    returns = [Parameter(int, "1 if successful")]
    
    def call(self, ticket, creds):
        valid_creds = self.api.auth.checkCredentials(cred, 'redeemticket')
        self.api.auth.check_ticket(ticket)

        
        # send the call to the right manager
        manager = self.api.get_interface_manager()
        manager.redeem_ticket(self.api, ticket) 
        return 1 
