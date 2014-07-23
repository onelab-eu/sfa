#
# SfaAPI authentication 
#
import sys
from types import StringTypes

from sfa.util.faults import InsufficientRights, MissingCallerGID, MissingTrustedRoots, PermissionError, \
    BadRequestHash, ConnectionKeyGIDMismatch, SfaPermissionDenied, CredentialNotVerifiable, Forbidden, \
    BadArgs
from sfa.util.sfalogging import logger
from sfa.util.config import Config
from sfa.util.xrn import Xrn, get_authority

from sfa.trust.gid import GID
from sfa.trust.rights import Rights
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential
from sfa.trust.trustedroots import TrustedRoots
from sfa.trust.hierarchy import Hierarchy
from sfa.trust.sfaticket import SfaTicket
from sfa.trust.speaksfor_util import determine_speaks_for


class Auth:
    """
    Credential based authentication
    """

    def __init__(self, peer_cert = None, config = None ):
        self.peer_cert = peer_cert
        self.hierarchy = Hierarchy()
        if not config:
            self.config = Config()
        self.load_trusted_certs()

    def load_trusted_certs(self):
        self.trusted_cert_list = TrustedRoots(self.config.get_trustedroots_dir()).get_list()
        self.trusted_cert_file_list = TrustedRoots(self.config.get_trustedroots_dir()).get_file_list()

    # this convenience methods extracts speaking_for_xrn from the passed options using 'geni_speaking_for'
    def checkCredentialsSpeaksFor (self, *args, **kwds):
        if 'options' not in kwds:
            logger.error ("checkCredentialsSpeaksFor was not passed options=options")
            return
        # remove the options arg
        options=kwds['options']; del kwds['options']
        # compute the speaking_for_xrn arg and pass it to checkCredentials
        if options is None: speaking_for_xrn=None
        else:               speaking_for_xrn=options.get('geni_speaking_for',None)
        kwds['speaking_for_xrn']=speaking_for_xrn
        return self.checkCredentials (*args, **kwds)

    # do not use mutable as default argument 
    # http://docs.python-guide.org/en/latest/writing/gotchas/#mutable-default-arguments
    def checkCredentials(self, creds, operation, xrns=None, 
                         check_sliver_callback=None, 
                         speaking_for_xrn=None):
        if xrns is None: xrns=[]
        def log_invalid_cred(cred):
            if not isinstance (cred, StringTypes):
                logger.info("cannot validate credential %s - expecting a string"%cred)
                error="checkCredentials: expected a string, received %s"%(type(cred))
            else:
                cred_obj=Credential(string=cred)
                logger.info("failed to validate credential - dump=%s"%cred_obj.dump_string(dump_parents=True))
                error = sys.exc_info()[:2]
            return error

        # if xrns are specified they cannot be None or empty string
        if xrns:
            for xrn in xrns:
                if not xrn:
                    raise BadArgs("Invalid urn or hrn")

        
        if not isinstance(xrns, list):
            xrns = [xrns]

        slice_xrns = Xrn.filter_type(xrns, 'slice')
        sliver_xrns = Xrn.filter_type(xrns, 'sliver')

        # we are not able to validate slivers in the traditional way so 
        # we make sure not to include sliver urns/hrns in the core validation loop
        hrns = [Xrn(xrn).hrn for xrn in xrns if xrn not in sliver_xrns] 
        valid = []
        if not isinstance(creds, list):
            creds = [creds]
        logger.debug("Auth.checkCredentials with %d creds on hrns=%s"%(len(creds),hrns))
        # won't work if either creds or hrns is empty - let's make it more explicit
        if not creds: raise Forbidden("no credential provided")
        if not hrns: hrns = [None]
        error=[None,None]

        speaks_for_gid = determine_speaks_for(logger, creds, self.peer_cert,
                                              speaking_for_xrn, self.trusted_cert_list)

        if self.peer_cert and \
           not self.peer_cert.is_pubkey(speaks_for_gid.get_pubkey()):
            valid = creds
        else:
            for cred in creds:
                for hrn in hrns:
                    try:
                        self.check(cred, operation, hrn)
                        valid.append(cred)
                    except:
                        error = log_invalid_cred(cred)
        
        # make sure all sliver xrns are validated against the valid credentials
        if sliver_xrns:
            if not check_sliver_callback:
                msg = "sliver verification callback method not found." 
                msg += " Unable to validate sliver xrns: %s" % sliver_xrns
                raise Forbidden(msg)
            check_sliver_callback(valid, sliver_xrns)
                
        if not len(valid):
            raise Forbidden("Invalid credential %s -- %s"%(error[0],error[1]))
        
        return valid
        
        
    def check(self, credential, operation, hrn = None):
        """
        Check the credential against the peer cert (callerGID included 
        in the credential matches the caller that is connected to the 
        HTTPS connection, check if the credential was signed by a 
        trusted cert and check if the credential is allowed to perform 
        the specified operation.    
        """
        cred = Credential(cred=credential)    
        self.client_cred = cred
        logger.debug("Auth.check: handling hrn=%s and credential=%s"%\
                         (hrn,cred.get_summary_tostring()))

        if cred.type not in ['geni_sfa']:
            raise CredentialNotVerifiable(cred.type, "%s not supported" % cred.type)
        self.client_gid = self.client_cred.get_gid_caller()
        self.object_gid = self.client_cred.get_gid_object()
        
        # make sure the client_gid is not blank
        if not self.client_gid:
            raise MissingCallerGID(self.client_cred.get_subject())
       
        # validate the client cert if it exists
        if self.peer_cert:
            self.verifyPeerCert(self.peer_cert, self.client_gid)                   

        # make sure the client is allowed to perform the operation
        if operation:
            if not self.client_cred.can_perform(operation):
                raise InsufficientRights(operation)

        if self.trusted_cert_list:
            self.client_cred.verify(self.trusted_cert_file_list, self.config.SFA_CREDENTIAL_SCHEMA)
        else:
           raise MissingTrustedRoots(self.config.get_trustedroots_dir())
       
        # Make sure the credential's target matches the specified hrn. 
        # This check does not apply to trusted peers 
        trusted_peers = [gid.get_hrn() for gid in self.trusted_cert_list]
        if hrn and self.client_gid.get_hrn() not in trusted_peers:
            target_hrn = self.object_gid.get_hrn()
            if not hrn == target_hrn:
                raise PermissionError("Target hrn: %s doesn't match specified hrn: %s " % \
                                       (target_hrn, hrn) )       
        return True

    def check_ticket(self, ticket):
        """
        Check if the tickt was signed by a trusted cert
        """
        if self.trusted_cert_list:
            client_ticket = SfaTicket(string=ticket)
            client_ticket.verify_chain(self.trusted_cert_list)
        else:
           raise MissingTrustedRoots(self.config.get_trustedroots_dir())

        return True 

    def verifyPeerCert(self, cert, gid):
        # make sure the client_gid matches client's certificate
        if not cert.is_pubkey(gid.get_pubkey()):
            raise ConnectionKeyGIDMismatch(gid.get_subject()+":"+cert.get_subject())            

    def verifyGidRequestHash(self, gid, hash, arglist):
        key = gid.get_pubkey()
        if not key.verify_string(str(arglist), hash):
            raise BadRequestHash(hash)

    def verifyCredRequestHash(self, cred, hash, arglist):
        gid = cred.get_gid_caller()
        self.verifyGidRequestHash(gid, hash, arglist)

    def validateGid(self, gid):
        if self.trusted_cert_list:
            gid.verify_chain(self.trusted_cert_list)

    def validateCred(self, cred):
        if self.trusted_cert_list:
            cred.verify(self.trusted_cert_file_list)

    def authenticateGid(self, gidStr, argList, requestHash=None):
        gid = GID(string = gidStr)
        self.validateGid(gid)
        # request_hash is optional
        if requestHash:
            self.verifyGidRequestHash(gid, requestHash, argList)
        return gid

    def authenticateCred(self, credStr, argList, requestHash=None):
        cred = Credential(string = credStr)
        self.validateCred(cred)
        # request hash is optional
        if requestHash:
            self.verifyCredRequestHash(cred, requestHash, argList)
        return cred

    def authenticateCert(self, certStr, requestHash):
        cert = Certificate(string=certStr)
        # xxx should be validateCred ??
        self.validateCred(cert)   

    def gidNoop(self, gidStr, value, requestHash):
        self.authenticateGid(gidStr, [gidStr, value], requestHash)
        return value

    def credNoop(self, credStr, value, requestHash):
        self.authenticateCred(credStr, [credStr, value], requestHash)
        return value

    def verify_cred_is_me(self, credential):
        is_me = False 
        cred = Credential(string=credential)
        caller_gid = cred.get_gid_caller()
        caller_hrn = caller_gid.get_hrn()
        if caller_hrn != self.config.SFA_INTERFACE_HRN:
            raise SfaPermissionDenied(self.config.SFA_INTEFACE_HRN)

        return   
        
    def get_auth_info(self, auth_hrn):
        """
        Given an authority name, return the information for that authority.
        This is basically a stub that calls the hierarchy module.
        
        @param auth_hrn human readable name of authority  
        """

        return self.hierarchy.get_auth_info(auth_hrn)


    def veriry_auth_belongs_to_me(self, name):
        """
        Verify that an authority belongs to our hierarchy. 
        This is basically left up to the implementation of the hierarchy
        module. If the specified name does not belong, ane exception is 
        thrown indicating the caller should contact someone else.

        @param auth_name human readable name of authority
        """

        # get auth info will throw an exception if the authority doesnt exist
        self.get_auth_info(name)


    def verify_object_belongs_to_me(self, name):
        """
        Verify that an object belongs to our hierarchy. By extension,
        this implies that the authority that owns the object belongs
        to our hierarchy. If it does not an exception is thrown.
    
        @param name human readable name of object        
        """
        auth_name = self.get_authority(name)
        if not auth_name:
            auth_name = name 
        if name == self.config.SFA_INTERFACE_HRN:
            return
        self.verify_auth_belongs_to_me(auth_name) 
             
    def verify_auth_belongs_to_me(self, name):
        # get auth info will throw an exception if the authority doesnt exist
        self.get_auth_info(name) 


    def verify_object_permission(self, name):
        """
        Verify that the object gid that was specified in the credential
        allows permission to the object 'name'. This is done by a simple
        prefix test. For example, an object_gid for plc.arizona would 
        match the objects plc.arizona.slice1 and plc.arizona.
    
        @param name human readable name to test  
        """
        object_hrn = self.object_gid.get_hrn()
        if object_hrn == name:
            return
        if name.startswith(object_hrn + "."):
            return
        #if name.startswith(get_authority(name)):
            #return
    
        raise PermissionError(name)

    def determine_user_rights(self, caller_hrn, reg_record):
        """
        Given a user credential and a record, determine what set of rights the
        user should have to that record.
        
        This is intended to replace determine_user_rights() and
        verify_cancreate_credential()
        """

        rl = Rights()
        type = reg_record.type

        logger.debug("entering determine_user_rights with record %s and caller_hrn %s"%(reg_record, caller_hrn))

        if type == 'slice':
            # researchers in the slice are in the DB as-is
            researcher_hrns = [ user.hrn for user in reg_record.reg_researchers ]
            # locating PIs attached to that slice
            slice_pis=reg_record.get_pis()
            pi_hrns = [ user.hrn for user in slice_pis ]
            if (caller_hrn in researcher_hrns + pi_hrns):
                rl.add('refresh')
                rl.add('embed')
                rl.add('bind')
                rl.add('control')
                rl.add('info')

        elif type == 'authority':
            pi_hrns = [ user.hrn for user in reg_record.reg_pis ]
            if (caller_hrn == self.config.SFA_INTERFACE_HRN):
                rl.add('authority')
                rl.add('sa')
                rl.add('ma')
            if (caller_hrn in pi_hrns):
                rl.add('authority')
                rl.add('sa')
            # NOTE: for the PL implementation, this 'operators' list 
            # amounted to users with 'tech' role in that site 
            # it seems like this is not needed any longer, so for now I just drop that
            # operator_hrns = reg_record.get('operator',[])
            # if (caller_hrn in operator_hrns):
            #    rl.add('authority')
            #    rl.add('ma')

        elif type == 'user':
            rl.add('refresh')
            rl.add('resolve')
            rl.add('info')

        elif type == 'node':
            rl.add('operator')

        return rl

    def get_authority(self, hrn):
        return get_authority(hrn)

    def filter_creds_by_caller(self, creds, caller_hrn_list):
        """
        Returns a list of creds who's gid caller matches the 
        specified caller hrn
        """
        if not isinstance(creds, list):
            creds = [creds]
        creds = []
        if not isinstance(caller_hrn_list, list):
            caller_hrn_list = [caller_hrn_list]
        for cred in creds:
            try:
                tmp_cred = Credential(string=cred)
                if tmp_cred.get_gid_caller().get_hrn() in [caller_hrn_list]:
                    creds.append(cred)
            except: pass
        return creds

