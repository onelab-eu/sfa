# XMLRPC-specific code for SFA Client

# starting with 2.7.9 we need to turn off server verification
import ssl
ssl_needs_unverified_context = hasattr(ssl, '_create_unverified_context')

import xmlrpclib
from httplib import HTTPS, HTTPSConnection

try:
    from sfa.util.sfalogging import logger
except:
    import logging
    logger = logging.getLogger('sfaserverproxy')

##
# ServerException, ExceptionUnmarshaller
#
# Used to convert server exception strings back to an exception.
#    from usenet, Raghuram Devarakonda

class ServerException(Exception):
    pass

class ExceptionUnmarshaller(xmlrpclib.Unmarshaller):
    def close(self):
        try:
            return xmlrpclib.Unmarshaller.close(self)
        except xmlrpclib.Fault, e:
            raise ServerException(e.faultString)

##
# XMLRPCTransport
#
# A transport for XMLRPC that works on top of HTTPS

# targetting only python-2.7 we can get rid of some older code

class XMLRPCTransport(xmlrpclib.Transport):
    
    def __init__(self, key_file = None, cert_file = None, timeout = None):
        xmlrpclib.Transport.__init__(self)
        self.timeout=timeout
        self.key_file = key_file
        self.cert_file = cert_file
        
    def make_connection(self, host):
        # create a HTTPS connection object from a host descriptor
        # host may be a string, or a (host, x509-dict) tuple
        host, extra_headers, x509 = self.get_host_info(host)
        if not ssl_needs_unverified_context:
            conn = HTTPSConnection(host, None, key_file = self.key_file,
                                   cert_file = self.cert_file)
        else:
            conn = HTTPSConnection(host, None, key_file = self.key_file,
                                   cert_file = self.cert_file,
                                   context = ssl._create_unverified_context())

        # Some logic to deal with timeouts. It appears that some (or all) versions
        # of python don't set the timeout after the socket is created. We'll do it
        # ourselves by forcing the connection to connect, finding the socket, and
        # calling settimeout() on it. (tested with python 2.6)
        if self.timeout:
            if hasattr(conn, 'set_timeout'):
                conn.set_timeout(self.timeout)

            if hasattr(conn, "_conn"):
                # HTTPS is a wrapper around HTTPSConnection
                real_conn = conn._conn
            else:
                real_conn = conn
            conn.connect()
            if hasattr(real_conn, "sock") and hasattr(real_conn.sock, "settimeout"):
                real_conn.sock.settimeout(float(self.timeout))

        return conn

    def getparser(self):
        unmarshaller = ExceptionUnmarshaller()
        parser = xmlrpclib.ExpatParser(unmarshaller)
        return parser, unmarshaller

class XMLRPCServerProxy(xmlrpclib.ServerProxy):
    def __init__(self, url, transport, allow_none=True, verbose=False):
        # remember url for GetVersion
        # xxx not sure this is still needed as SfaServerProxy has this too
        self.url=url
        if not ssl_needs_unverified_context:
            xmlrpclib.ServerProxy.__init__(self, url, transport, allow_none=allow_none,
                                           verbose=verbose)
        else:
            xmlrpclib.ServerProxy.__init__(self, url, transport, allow_none=allow_none,
                                           verbose=verbose,
                                           context=ssl._create_unverified_context())

    def __getattr__(self, attr):
        logger.debug ("xml-rpc %s method:%s" % (self.url, attr))
        return xmlrpclib.ServerProxy.__getattr__(self, attr)

########## the object on which we can send methods that get sent over xmlrpc
class SfaServerProxy:

    def __init__ (self, url, keyfile, certfile, verbose=False, timeout=None):
        self.url = url
        self.keyfile = keyfile
        self.certfile = certfile
        self.verbose = verbose
        self.timeout = timeout
        # an instance of xmlrpclib.ServerProxy
        transport = XMLRPCTransport(keyfile, certfile, timeout)
        self.serverproxy = XMLRPCServerProxy(url, transport, allow_none=True, verbose=verbose)

    # this is python magic to return the code to run when 
    # SfaServerProxy receives a method call
    # so essentially we send the same method with identical arguments
    # to the server_proxy object
    def __getattr__(self, name):
        def func(*args, **kwds):
            return getattr(self.serverproxy, name)(*args, **kwds)
        return func

