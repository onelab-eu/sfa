# Thierry Parmentelat -- INRIA
#
# a minimal library for writing "lightweight" SFA clients
#

import os,os.path

import sfa.util.sfalogging

# what we use on GID actually is inherited from Certificate
#from sfa.trust.gid import GID
from sfa.trust.certificate import Keypair, Certificate
# what we need in the Credential class essentially amounts to saving the incoming result
# in a file as the output from the registry already is under xml format
#from sfa.trust.credential import Credential

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

    #################### public interface

    # xxx should that be called in the constructor ?
    # typically user_private_key is ~/.ssh/id_rsa
    def init_private_key_if_missing (self, user_private_key):
        private_key_filename=self.private_key_filename()
        if not os.path.isfile (private_key_filename):
            key=self.plain_read(user_private_key)
            self.plain_write(private_key_filename, key)
            os.chmod(private_key_filename,os.stat(user_private_key).st_mode)
            self.logger.debug("SfaClientBootstrap: Copied private key from %s into %s"%\
                                  (user_private_key,private_key_filename))
        
    # make sure we have the GID at hand
    def bootstrap_gid (self):
        if self.any_certificate_filename() is None:
            self.get_self_signed_cert()
        self.get_credential()
        self.get_gid()

    def server_proxy (self, url):
        return SfaServerProxy (url, self.private_key_filename(), self.gid_filename())

    def get_credential_string (self):
        return self.plain_read (self.get_credential())

    # more to come to get credentials about other objects (authority/slice)

    #################### private details
    # stupid stuff
    def fullpath (self, file): return os.path.join (self.dir,file)
    # %s -> self.hrn
    def fullpath_format(self,format): return self.fullpath (format%self.hrn)

    def private_key_filename (self): 
        return self.fullpath_format ("%s.pkey")
    def self_signed_cert_filename (self): 
        return self.fullpath_format ("%s.sscert")
    def credential_filename (self): 
        return self.fullpath_format ("%s.user.cred")
    def gid_filename (self): 
        return self.fullpath_format ("%s.user.gid")

# optimizing dependencies
# originally we used classes GID or Credential or Certificate 
# like e.g. 
#        return Credential(filename=self.get_credential()).save_to_string()
# but in order to make it simpler to other implementations/languages..
    def plain_read (self, filename):
        infile=file(filename,"r")
        result=infile.read()
        infile.close()
        return result

    def plain_write (self, filename, contents):
        outfile=file(filename,"w")
        result=outfile.write(contents)
        outfile.close()

    # the private key
    def check_private_key (self):
        if not os.path.isfile (self.private_key_filename()):
            raise Exception,"No such file %s"%self.private_key_filename()
        return True

    # get any certificate
    # rationale  for this method, once we have the gid, it's actually safe
    # to remove the .sscert
    def any_certificate_filename (self):
        attempts=[ self.gid_filename(), self.self_signed_cert_filename() ]
        for attempt in attempts:
            if os.path.isfile (attempt): return attempt
        return None

    ### step1
    # unconditionnally
    def create_self_signed_certificate (self,output):
        self.check_private_key()
        private_key_filename = self.private_key_filename()
        keypair=Keypair(filename=private_key_filename)
        self_signed = Certificate (subject = self.hrn)
        self_signed.set_pubkey (keypair)
        self_signed.set_issuer (keypair, self.hrn)
        self_signed.sign ()
        self_signed.save_to_file (output)
        self.logger.debug("SfaClientBootstrap: Created self-signed certificate for %s in %s"%\
                              (self.hrn,output))
        return output

    def get_self_signed_cert (self):
        self_signed_cert_filename = self.self_signed_cert_filename()
        if os.path.isfile (self_signed_cert_filename):
            return self_signed_cert_filename
        return self.create_self_signed_certificate(self_signed_cert_filename)
        
    ### step2 
    # unconditionnally
    def retrieve_credential (self, output):
        self.check_private_key()
        certificate_filename = self.any_certificate_filename()
        certificate_string = self.plain_read (certificate_filename)
        registry_proxy = SfaServerProxy (self.registry_url, self.private_key_filename(),
                                         certificate_filename)
        credential_string=registry_proxy.GetSelfCredential (certificate_string, self.hrn, "user")
        self.plain_write (output, credential_string)
        self.logger.debug("SfaClientBootstrap: Wrote result of GetSelfCredential in %s"%output)
        return output

    def get_credential (self):
        credential_filename = self.credential_filename ()
        if os.path.isfile(credential_filename): 
            return credential_filename
        return self.retrieve_credential (credential_filename)

    ### step3
    # unconditionnally
    def retrieve_gid (self, hrn, type, output):
         self.check_private_key()
         certificate_filename = self.any_certificate_filename()
         registry_proxy = SfaServerProxy (self.registry_url, self.private_key_filename(),
                                          certificate_filename)
         credential_string=self.plain_read (self.get_credential())
         records = registry_proxy.Resolve (hrn, credential_string)
         records=[record for record in records if record['type']==type]
         if not records:
             # RecordNotFound
             raise Exception, "hrn %s (%s) unknown to registry %s"%(hrn,type,self.registry_url)
         record=records[0]
         self.plain_write (output, record['gid'])
         self.logger.debug("SfaClientBootstrap: Wrote GID for %s (%s) in %s"% (hrn,type,output))
         return output

    def get_gid (self):
        gid_filename=self.gid_filename()
        if os.path.isfile(gid_filename): 
            return gid_filename
        return self.retrieve_gid(self.hrn, "user", gid_filename)

