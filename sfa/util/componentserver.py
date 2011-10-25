##
# This module implements a general-purpose server layer for sfa.
# The same basic server should be usable on the registry, component, or
# other interfaces.
#
# TODO: investigate ways to combine this with existing PLC server?
##

import sys
import traceback
import threading
import socket, os
import SocketServer
import BaseHTTPServer
import SimpleHTTPServer
import SimpleXMLRPCServer
from OpenSSL import SSL

from sfa.util.sfalogging import logger
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import *
from sfa.util.faults import *
from sfa.plc.api import ComponentAPI 
from sfa.server.sfaserver import verify_callback, ThreadedServer 


##
# taken from the web (XXX find reference). Implents HTTPS xmlrpc request handler

class SecureXMLRpcRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    """Secure XML-RPC request handler class.

    It it very similar to SimpleXMLRPCRequestHandler but it uses HTTPS for transporting XML data.
    """
    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

    def do_POST(self):
        """Handles the HTTPS POST request.

        It was copied out from SimpleXMLRPCServer.py and modified to shutdown the socket cleanly.
        """
        try:
            peer_cert = Certificate()
            peer_cert.load_from_pyopenssl_x509(self.connection.get_peer_certificate())
            self.api = ComponentAPI(peer_cert = peer_cert, 
                           interface = self.server.interface, 
                           key_file = self.server.key_file, 
                           cert_file = self.server.cert_file)
            # get arguments
            request = self.rfile.read(int(self.headers["content-length"]))
            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and dispatch
            # using that method if present.
            #response = self.server._marshaled_dispatch(request, getattr(self, '_dispatch', None))
            # XX TODO: Need to get the real remote address
            remote_addr = (remote_ip, remote_port) = self.connection.getpeername()
            self.api.remote_addr = remote_addr
            #remote_addr = (self.rfile.connection.remote_ip, remote_port)
            #self.api.remote_addr = remote_addr
            response = self.api.handle(remote_addr, request)

        
        except Exception, fault:
            raise
            # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            self.send_response(500)
            self.end_headers()
            logger.log_exc("componentserver.SecureXMLRpcRequestHandler.do_POST")
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown() # Modified here!

##
# Implements an HTTPS XML-RPC server. Generally it is expected that SFA
# functions will take a credential string, which is passed to
# decode_authentication. Decode_authentication() will verify the validity of
# the credential, and verify that the user is using the key that matches the
# GID supplied in the credential.

class ComponentServer(threading.Thread):

    ##
    # Create a new SfaServer object.
    #
    # @param ip the ip address to listen on
    # @param port the port to listen on
    # @param key_file private key filename of registry
    # @param cert_file certificate filename containing public key 
    #   (could be a GID file)

    def __init__(self, ip, port, key_file, cert_file, api=None):
        threading.Thread.__init__(self)
        self.key = Keypair(filename = key_file)
        self.cert = Certificate(filename = cert_file)
        self.server = ThreadedServer((ip, port), SecureXMLRpcRequestHandler, key_file, cert_file)
        self.trusted_cert_list = None
        self.register_functions()


    ##
    # Register functions that will be served by the XMLRPC server. This
    # function should be overrided by each descendant class.

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


