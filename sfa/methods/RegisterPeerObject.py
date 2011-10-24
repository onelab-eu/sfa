from sfa.trust.certificate import Keypair, convert_public_key
from sfa.trust.gid import *

from sfa.util.faults import *
from sfa.util.xrn import get_authority
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.record import SfaRecord
from sfa.util.table import SfaTable
from sfa.trust.auth import Auth
from sfa.trust.gid import create_uuid
from sfa.trust.credential import Credential

class RegisterPeerObject(Method):
    """
    Register a peer object with the registry. In addition to being stored in the
    SFA database, the appropriate records will also be created in the
    PLC databases
    
    @param cred credential string
    @param record_dict dictionary containing record fields
    @return gid string representation
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(dict, "Record dictionary containing record fields"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, cred, record_dict, origin_hrn=None):
        user_cred = Credential(string=cred)

        #log the call
        if not origin_hrn:
            origin_hrn = user_cred.get_gid_caller().get_hrn()    
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, None, self.name))

        # validate the cred
        self.api.auth.check(cred, "register")

        # make sure this is a peer record
        if 'peer_authority' not in record_dict or \
           not record_dict['peer_authority']: 
            raise SfaInvalidArgument, "peer_authority must be specified" 

        record = SfaRecord(dict = record_dict)
        type, hrn, peer_authority = record['type'], record['hrn'], record['peer_authority']
        record['authority'] = get_authority(record['hrn'])
        # verify permissions
        self.api.auth.verify_cred_is_me(cred)

        # check if record already exists
        table = SfaTable()
        existing_records = table.find({'type': type, 'hrn': hrn, 'peer_authority': peer_authority})
        if existing_records:
            for existing_record in existing_records:
                if existing_record['pointer'] != record['pointer']:
                    record['record_id'] = existing_record['record_id']
                    table.update(record)
        else:
            record_id = table.insert(record)
 
        return 1
