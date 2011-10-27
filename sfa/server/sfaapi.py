from sfa.util.faults import SfaAPIError
from sfa.util.config import Config
from sfa.util.cache import Cache
from sfa.trust.auth import Auth
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential
# this is wrong all right, but temporary 
from sfa.managers.managerwrapper import ManagerWrapper, import_manager
from sfa.server.xmlrpcapi import XmlrpcApi
import os
import datetime

####################
class SfaApi (XmlrpcApi): 
    
    """
    An SfaApi instance is a basic xmlrcp service
    augmented with the local cryptographic material and hrn
    It also has the notion of neighbour sfa services 
    as defined in /etc/sfa/{aggregates,registries}.xml
    It has no a priori knowledge of the underlying testbed
    """

    def __init__ (self, encoding="utf-8", methods='sfa.methods', 
                  config = "/etc/sfa/sfa_config.py", 
                  peer_cert = None, interface = None, 
                  key_file = None, cert_file = None, cache = None):
        
        XmlrpcApi.__init__ (self, encoding)
        
        # we may be just be documenting the API
        if config is None:
            return
        # Load configuration
        self.config = Config(config)
        self.auth = Auth(peer_cert)
        self.interface = interface
        self.hrn = self.config.SFA_INTERFACE_HRN
        self.key_file = key_file
        self.key = Keypair(filename=self.key_file)
        self.cert_file = cert_file
        self.cert = Certificate(filename=self.cert_file)
        self.cache = cache
        if self.cache is None:
            self.cache = Cache()
        self.credential = None

        # load registries
        from sfa.server.registry import Registries
        self.registries = Registries() 

        # load aggregates
        from sfa.server.aggregate import Aggregates
        self.aggregates = Aggregates()


    def get_interface_manager(self, manager_base = 'sfa.managers'):
        """
        Returns the appropriate manager module for this interface.
        Modules are usually found in sfa/managers/
        """
        manager=None
        if self.interface in ['registry']:
            manager=import_manager ("registry",  self.config.SFA_REGISTRY_TYPE)
        elif self.interface in ['aggregate']:
            manager=import_manager ("aggregate", self.config.SFA_AGGREGATE_TYPE)
        elif self.interface in ['slicemgr', 'sm']:
            manager=import_manager ("slice",     self.config.SFA_SM_TYPE)
        elif self.interface in ['component', 'cm']:
            manager=import_manager ("component", self.config.SFA_CM_TYPE)
        if not manager:
            raise SfaAPIError("No manager for interface: %s" % self.interface)  
            
        # this isnt necessary but will help to produce better error messages
        # if someone tries to access an operation this manager doesn't implement  
        manager = ManagerWrapper(manager, self.interface)

        return manager

    def get_server(self, interface, cred, timeout=30):
        """
        Returns a connection to the specified interface. Use the specified
        credential to determine the caller and look for the caller's key/cert 
        in the registry hierarchy cache. 
        """       
        from sfa.trust.hierarchy import Hierarchy
        if not isinstance(cred, Credential):
            cred_obj = Credential(string=cred)
        else:
            cred_obj = cred
        caller_gid = cred_obj.get_gid_caller()
        hierarchy = Hierarchy()
        auth_info = hierarchy.get_auth_info(caller_gid.get_hrn())
        key_file = auth_info.get_privkey_filename()
        cert_file = auth_info.get_gid_filename()
        server = interface.get_server(key_file, cert_file, timeout)
        return server
               
        
    def getCredential(self):
        """
        Return a valid credential for this interface. 
        """
        type = 'authority'
        path = self.config.SFA_DATA_DIR
        filename = ".".join([self.interface, self.hrn, type, "cred"])
        cred_filename = path + os.sep + filename
        cred = None
        if os.path.isfile(cred_filename):
            cred = Credential(filename = cred_filename)
            # make sure cred isnt expired
            if not cred.get_expiration or \
               datetime.datetime.utcnow() < cred.get_expiration():    
                return cred.save_to_string(save_parents=True)

        # get a new credential
        if self.interface in ['registry']:
            cred =  self.__getCredentialRaw()
        else:
            cred =  self.__getCredential()
        cred.save_to_file(cred_filename, save_parents=True)

        return cred.save_to_string(save_parents=True)


    def getDelegatedCredential(self, creds):
        """
        Attempt to find a credential delegated to us in
        the specified list of creds.
        """
        from sfa.trust.hierarchy import Hierarchy
        if creds and not isinstance(creds, list): 
            creds = [creds]
        hierarchy = Hierarchy()
                
        delegated_cred = None
        for cred in creds:
            if hierarchy.auth_exists(Credential(string=cred).get_gid_caller().get_hrn()):
                delegated_cred = cred
                break
        return delegated_cred
 
    def __getCredential(self):
        """ 
        Get our credential from a remote registry 
        """
        from sfa.server.registry import Registries
        registries = Registries()
        registry = registries.get_server(self.hrn, self.key_file, self.cert_file)
        cert_string=self.cert.save_to_string(save_parents=True)
        # get self credential
        self_cred = registry.GetSelfCredential(cert_string, self.hrn, 'authority')
        # get credential
        cred = registry.GetCredential(self_cred, self.hrn, 'authority')
        return Credential(string=cred)

    def __getCredentialRaw(self):
        """
        Get our current credential directly from the local registry.
        """

        hrn = self.hrn
        auth_hrn = self.auth.get_authority(hrn)
    
        # is this a root or sub authority
        if not auth_hrn or hrn == self.config.SFA_INTERFACE_HRN:
            auth_hrn = hrn
        auth_info = self.auth.get_auth_info(auth_hrn)
        table = self.SfaTable()
        records = table.findObjects({'hrn': hrn, 'type': 'authority+sa'})
        if not records:
            raise RecordNotFound
        record = records[0]
        type = record['type']
        object_gid = record.get_gid_object()
        new_cred = Credential(subject = object_gid.get_subject())
        new_cred.set_gid_caller(object_gid)
        new_cred.set_gid_object(object_gid)
        new_cred.set_issuer_keys(auth_info.get_privkey_filename(), auth_info.get_gid_filename())
        
        r1 = determine_rights(type, hrn)
        new_cred.set_privileges(r1)
        new_cred.encode()
        new_cred.sign()

        return new_cred
   
    def loadCredential (self):
        """
        Attempt to load credential from file if it exists. If it doesnt get
        credential from registry.
        """

        # see if this file exists
        # XX This is really the aggregate's credential. Using this is easier than getting
        # the registry's credential from iteslf (ssl errors).   
        ma_cred_filename = self.config.SFA_DATA_DIR + os.sep + self.interface + self.hrn + ".ma.cred"
        try:
            self.credential = Credential(filename = ma_cred_filename)
        except IOError:
            self.credential = self.getCredentialFromRegistry()

    def get_cached_server_version(self, server):
        cache_key = server.url + "-version"
        server_version = None
        if self.cache:
            server_version = self.cache.get(cache_key)
        if not server_version:
            server_version = server.GetVersion()
            # cache version for 24 hours
            self.cache.add(cache_key, server_version, ttl= 60*60*24)
        return server_version
