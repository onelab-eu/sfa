#
# a minimal library for writing "lightweight" SFA clients
#

import os,os.path

import sfa.util.sfalogging

from sfa.trust.gid import GID
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential

import sfa.client.sfaprotocol as sfaprotocol

class SfaServerProxy:

    def __init__ (self, url, keyfile, certfile, verbose=False, timeout=None):
        self.url=url
        self.keyfile=keyfile
        self.certfile=certfile
        self.verbose=verbose
        self.timeout=timeout
        # an instance of xmlrpclib.ServerProxy
        self.serverproxy=sfaprotocol.server_proxy \
            (self.url, self.keyfile, self.certfile, self.timeout, self.verbose)

    # this is python magic to return the code to run when 
    # SfaServerProxy receives a method call
    # so essentially we send the same method with identical arguments
    # to the server_proxy object
    def __getattr__(self, name):
        def func(*args, **kwds):
            return getattr(self.serverproxy, name)(*args, **kwds)
        return func
    

########## 
# a helper class to implement the bootstrapping of crypto. material
# assuming we are starting from scratch on the client side 
# what's needed to complete a full slice creation cycle
# (**) prerequisites: 
#  (*) a local private key 
#  (*) the corresp. public key in the registry 
# (**) step1: a self-signed certificate
#      default filename is <hrn>.sscert
# (**) step2: a user credential
#      obtained at the registry with GetSelfCredential
#      using the self-signed certificate as the SSL cert
#      default filename is <hrn>.user.cred
# (**) step3: a registry-provided certificate (i.e. a GID)
#      obtained at the registry using Resolve
#      using the step2 credential as credential
#      default filename is <hrn>.user.gid
##########
# from that point on, the GID can/should be used as the SSL cert for anything
# a new (slice) credential would be needed for slice operations and can be 
# obtained at the registry through GetCredential

# xxx todo should protect against write file permissions
# xxx todo review exceptions
class SfaClientBootstrap:

    # xxx todo should account for verbose and timeout that the proxy offers
    def __init__ (self, user_hrn, registry_url, dir=None, logger=None):
        self.hrn=user_hrn
        self.registry_url=registry_url
        if dir is None: dir="."
        self.dir=dir
        if logger is None: 
            print 'special case for logger'
            logger = sfa.util.sfalogging.logger
        self.logger=logger
    
    # stupid stuff
    def fullpath (self, file): return os.path.join (self.dir,file)
    # %s -> self.hrn
    def fullpath_format(self,format): return self.fullpath (format%self.hrn)

    def private_key_file (self): 
        return self.fullpath_format ("%s.pkey")

    def self_signed_cert_file (self): 
        return self.fullpath_format ("%s.sscert")
    def credential_file (self): 
        return self.fullpath_format ("%s.user.cred")
    def gid_file (self): 
        return self.fullpath_format ("%s.user.gid")

    def check_private_key (self):
        if not os.path.isfile (self.private_key_file()):
            raise Exception,"No such file %s"%self.private_key_file()
        return True

    # typically user_private_key is ~/.ssh/id_rsa
    def init_private_key_if_missing (self, user_private_key):
        private_key_file=self.private_key_file()
        if not os.path.isfile (private_key_file):
            infile=file(user_private_key)
            outfile=file(private_key_file,'w')
            outfile.write(infile.read())
            outfile.close()
            infile.close()
            os.chmod(private_key_file,os.stat(user_private_key).st_mode)
            self.logger.debug("SfaClientBootstrap: Copied private key from %s into %s"%\
                                  (user_private_key,private_key_file))
        

    # get any certificate, gid preferred
    def preferred_certificate_file (self):
        attempts=[ self.gid_file(), self.self_signed_cert_file() ]
        for attempt in attempts:
            if os.path.isfile (attempt): return attempt
        return None

    ### step1
    # unconditionnally
    def create_self_signed_certificate (self,output):
        self.check_private_key()
        private_key_file = self.private_key_file()
        keypair=Keypair(filename=private_key_file)
        self_signed = Certificate (subject = self.hrn)
        self_signed.set_pubkey (keypair)
        self_signed.set_issuer (keypair, self.hrn)
        self_signed.sign ()
        self_signed.save_to_file (output)
        self.logger.debug("SfaClientBootstrap: Created self-signed certificate for %s in %s"%\
                              (self.hrn,output))
        return output

    def get_self_signed_cert (self):
        self_signed_cert_file = self.self_signed_cert_file()
        if os.path.isfile (self_signed_cert_file):
            return self_signed_cert_file
        return self.create_self_signed_certificate(self_signed_cert_file)
        
    ### step2 
    # unconditionnally
    def retrieve_credential (self, output):
        self.check_private_key()
        certificate_file = self.preferred_certificate_file()
        registry_proxy = SfaServerProxy (self.registry_url, self.private_key_file(),
                                         certificate_file)
        certificate = Certificate (filename=certificate_file)
        certificate_string = certificate.save_to_string(save_parents=True)
        credential_string=registry_proxy.GetSelfCredential (certificate_string, self.hrn, "user")
        credential = Credential (string=credential_string)
        credential.save_to_file (output, save_parents=True)
        self.logger.debug("SfaClientBootstrap: Wrote result of GetSelfCredential in %s"%output)
        return output

    def get_credential (self):
        credential_file = self.credential_file ()
        if os.path.isfile(credential_file): 
            return credential_file
        return self.retrieve_credential (credential_file)

    def get_credential_string (self):
        return Credential(filename=self.get_credential()).save_to_string()

    ### step3
    # unconditionnally
    def retrieve_gid (self, hrn, type, output):
         self.check_private_key()
         certificate_file = self.preferred_certificate_file()
         registry_proxy = SfaServerProxy (self.registry_url, self.private_key_file(),
                                          certificate_file)
         credential_string=Credential(filename=self.credential_file()).save_to_string()
         records = registry_proxy.Resolve (hrn, credential_string)
         records=[record for record in records if record['type']==type]
         if not records:
             # RecordNotFound
             raise Exception, "hrn %s (%s) unknown to registry %s"%(hrn,type,self.registry_url)
         record=records[0]
         gid=GID(string=record['gid'])
         gid.save_to_file (filename=output)
         self.logger.debug("SfaClientBootstrap: Wrote GID for %s (%s) in %s"% (hrn,type,output))
         return output

    def get_gid (self):
        gid_file=self.gid_file()
        if os.path.isfile(gid_file): 
            return gid_file
        return self.retrieve_gid(self.hrn, "user", gid_file)

    # make sure we have the GID at hand
    def bootstrap_gid (self):
        if self.preferred_certificate_file() is None:
            self.get_self_signed_cert()
        self.get_credential()
        self.get_gid()

    def server_proxy (self, url):
        return SfaServerProxy (url, self.private_key_file(), self.gid_file())

