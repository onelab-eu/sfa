import os
import tempfile

import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from sfa.util.nodemanager import NodeManager

from sfa.trust.credential import Credential
from sfa.trust.certificate import Certificate, Keypair
from sfa.trust.gid import GID

from sfa.server.sfaapi import SfaApi

####################
class PlcComponentApi(SfaApi):

    def __init__ (self, encoding="utf-8", methods='sfa.methods', 
                  config = "/etc/sfa/sfa_config.py", 
                  peer_cert = None, interface = None, 
                  key_file = None, cert_file = None, cache = None):
        SfaApi.__init__(self, encoding=encoding, methods=methods, 
                        config=config, 
                        peer_cert=peer_cert, interface=interface, 
                        key_file=key_file, 
                        cert_file=cert_file, cache=cache)

        self.nodemanager = NodeManager(self.config)

    def sliver_exists(self):
        sliver_dict = self.nodemanager.GetXIDs()
        ### xxx slicename is undefined
        if slicename in sliver_dict.keys():
            return True
        else:
            return False

    def get_registry(self):
        addr, port = self.config.SFA_REGISTRY_HOST, self.config.SFA_REGISTRY_PORT
        url = "http://%(addr)s:%(port)s" % locals()
        server = xmlrpcprotocol.get_server(url, self.key_file, self.cert_file)
        return server

    def get_node_key(self):
        # this call requires no authentication,
        # so we can generate a random keypair here
        subject="component"
        (kfd, keyfile) = tempfile.mkstemp()
        (cfd, certfile) = tempfile.mkstemp()
        key = Keypair(create=True)
        key.save_to_file(keyfile)
        cert = Certificate(subject=subject)
        cert.set_issuer(key=key, subject=subject)
        cert.set_pubkey(key)
        cert.sign()
        cert.save_to_file(certfile)
        registry = self.get_registry()
        # the registry will scp the key onto the node
        registry.get_key()        

    # override the method in SfaApi
    def getCredential(self):
        """
        Get our credential from a remote registry
        """
        path = self.config.SFA_DATA_DIR
        config_dir = self.config.config_path
        cred_filename = path + os.sep + 'node.cred'
        try:
            credential = Credential(filename = cred_filename)
            return credential.save_to_string(save_parents=True)
        except IOError:
            node_pkey_file = config_dir + os.sep + "node.key"
            node_gid_file = config_dir + os.sep + "node.gid"
            cert_filename = path + os.sep + 'server.cert'
            if not os.path.exists(node_pkey_file) or \
               not os.path.exists(node_gid_file):
                self.get_node_key()

            # get node's hrn
            gid = GID(filename=node_gid_file)
            hrn = gid.get_hrn()
            # get credential from registry
            cert_str = Certificate(filename=cert_filename).save_to_string(save_parents=True)
            registry = self.get_registry()
            cred = registry.GetSelfCredential(cert_str, hrn, 'node')
            # xxx credfile is undefined
            Credential(string=cred).save_to_file(credfile, save_parents=True)            

            return cred

    def clean_key_cred(self):
        """
        remove the existing keypair and cred  and generate new ones
        """
        files = ["server.key", "server.cert", "node.cred"]
        for f in files:
            # xxx KEYDIR is undefined, could be meant to be "/var/lib/sfa/" from sfa_component_setup.py
            filepath = KEYDIR + os.sep + f
            if os.path.isfile(filepath):
                os.unlink(f)

        # install the new key pair
        # GetCredential will take care of generating the new keypair
        # and credential
        self.get_node_key()
        self.getCredential()
