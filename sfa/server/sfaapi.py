import os, os.path
import datetime

from sfa.util.faults import SfaFault, SfaAPIError
from sfa.util.genicode import GENICODE
from sfa.util.config import Config
from sfa.util.cache import Cache
from sfa.trust.auth import Auth

from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential
from sfa.trust.rights import determine_rights

from sfa.server.xmlrpcapi import XmlrpcApi

from sfa.client.return_value import ReturnValue

# thgen xxx fixme this is wrong all right, but temporary, will use generic
from sfa.storage.table import SfaTable

####################
class SfaApi (XmlrpcApi): 
    
    """
    An SfaApi instance is a basic xmlrcp service
    augmented with the local cryptographic material and hrn

    It also has the notion of its own interface (a string describing
    whether we run a registry, aggregate or slicemgr) and has 
    the notion of neighbour sfa services as defined 
    in /etc/sfa/{aggregates,registries}.xml

    Finally it contains a cache instance

    It gets augmented by the generic layer with 
    (*) an instance of manager (actually a manager module for now)
    (*) which in turn holds an instance of a testbed driver
    For convenience api.manager.driver == api.driver
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
        self.credential = None
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

        # load registries
        from sfa.server.registry import Registries
        self.registries = Registries() 

        # load aggregates
        from sfa.server.aggregate import Aggregates
        self.aggregates = Aggregates()
        
        # filled later on by generic/Generic
        self.manager=None

    def server_proxy(self, interface, cred, timeout=30):
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
        server = interface.server_proxy(key_file, cert_file, timeout)
        return server
               
        
    def getCredential(self):
        """
        Return a valid credential for this interface. 
        """
        type = 'authority'
        path = self.config.SFA_DATA_DIR
        filename = ".".join([self.interface, self.hrn, type, "cred"])
        cred_filename = os.path.join(path,filename)
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
        registry = registries.server_proxy(self.hrn, self.key_file, self.cert_file)
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
        # xxx thgen fixme - use SfaTable hardwired for now 
        #table = self.SfaTable()
        table = SfaTable()
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
        filename = self.interface + self.hrn + ".ma.cred"
        ma_cred_path = os.path.join(self.config.SFA_DATA_DIR,filename)
        try:
            self.credential = Credential(filename = ma_cred_path)
        except IOError:
            self.credential = self.getCredentialFromRegistry()

    def get_cached_server_version(self, server):
        cache_key = server.url + "-version"
        server_version = None
        if self.cache:
            server_version = self.cache.get(cache_key)
        if not server_version:
            result = server.GetVersion()
            server_version = ReturnValue.get_value(result)
            # cache version for 24 hours
            self.cache.add(cache_key, server_version, ttl= 60*60*24)
        return server_version


    def get_geni_code(self, result):
        code = {
            'geni_code': GENICODE.SUCCESS, 
            'am_type': 'sfa',
            'am_code': None,
        }
        if isinstance(result, SfaFault):
            code['geni_code'] = result.faultCode
            code['am_code'] = result.faultCode                        
                
        return code

    def get_geni_value(self, result):
        value = result
        if isinstance(result, SfaFault):
            value = ""
        return value

    def get_geni_output(self, result):
        output = ""
        if isinstance(result, SfaFault):
            output = result.faultString 
        return output

    def prepare_response_v2_am(self, result):
        response = {
            'geni_api': 2,             
            'code': self.get_geni_code(result),
            'value': self.get_geni_value(result),
            'output': self.get_geni_output(result),
        }
        return response
    
    def prepare_response(self, result, method=""):
        """
        Converts the specified result into a standard GENI compliant 
        response  
        """
        # as of dec 13 2011 we only support API v2
        if self.interface.lower() in ['aggregate', 'slicemgr']: 
            result = self.prepare_response_v2_am(result)
        return XmlrpcApi.prepare_response(self, result, method)

