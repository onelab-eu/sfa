##
# This module implements a general-purpose server layer for sfa.
# The same basic server should be usable on the registry, component, or
# other interfaces.
#
# TODO: investigate ways to combine this with existing PLC server?
##

import threading

from sfa.server.threadedserver import ThreadedServer, SecureXMLRpcRequestHandler

from sfa.util.sfalogging import logger
from sfa.trust.certificate import Keypair, Certificate
#should be passed to threadedserver
#from sfa.plc.api import SfaAPI

##
# Implements an HTTPS XML-RPC server. Generally it is expected that SFA
# functions will take a credential string, which is passed to
# decode_authentication. Decode_authentication() will verify the validity of
# the credential, and verify that the user is using the key that matches the
# GID supplied in the credential.

class SfaServer(threading.Thread):

    ##
    # Create a new SfaServer object.
    #
    # @param ip the ip address to listen on
    # @param port the port to listen on
    # @param key_file private key filename of registry
    # @param cert_file certificate filename containing public key 
    #   (could be a GID file)

    def __init__(self, ip, port, key_file, cert_file,interface):
        threading.Thread.__init__(self)
        self.key = Keypair(filename = key_file)
        self.cert = Certificate(filename = cert_file)
        #self.server = SecureXMLRPCServer((ip, port), SecureXMLRpcRequestHandler, key_file, cert_file)
        self.server = ThreadedServer((ip, port), SecureXMLRpcRequestHandler, key_file, cert_file)
        self.server.interface=interface
        self.trusted_cert_list = None
        self.register_functions()
        logger.info("Starting SfaServer, interface=%s"%interface)

    ##
    # Register functions that will be served by the XMLRPC server. This
    # function should be overridden by each descendant class.

    def register_functions(self):
        self.server.register_function(self.noop)

    ##
    # Sample no-op server function. The no-op function decodes the credential
    # that was passed to it.

    def noop(self, cred, anything):
        self.decode_authentication(cred)
        return anything

    ##
    # Execute the server, serving requests forever. 

    def run(self):
        self.server.serve_forever()


