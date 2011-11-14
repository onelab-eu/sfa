# XMLRPC-specific code for SFA Client

import xmlrpclib
from httplib import HTTPS, HTTPSConnection

from sfa.util.sfalogging import logger

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

# python 2.7 xmlrpclib has changed its internal code
# it now calls 'getresponse' on the obj returned by make_connection
# while it used to call 'getreply'
# regardless of the version, httplib.HTTPS does implement getreply, 
# while httplib.HTTPSConnection has getresponse
# so we create a dummy instance to check what's expected
need_HTTPSConnection=hasattr(xmlrpclib.Transport().make_connection('localhost'),'getresponse')

class XMLRPCTransport(xmlrpclib.Transport):
    
    def __init__(self, key_file=None, cert_file=None, timeout=None):
        xmlrpclib.Transport.__init__(self)
        self.timeout=timeout
        self.key_file = key_file
        self.cert_file = cert_file
        
    def make_connection(self, host):
        # create a HTTPS connection object from a host descriptor
        # host may be a string, or a (host, x509-dict) tuple
        host, extra_headers, x509 = self.get_host_info(host)
        if need_HTTPSConnection:
            #conn = HTTPSConnection(host, None, key_file=self.key_file, cert_file=self.cert_file, timeout=self.timeout) #**(x509 or {}))
            conn = HTTPSConnection(host, None, key_file=self.key_file, cert_file=self.cert_file) #**(x509 or {}))
        else:
            #conn = HTTPS(host, None, key_file=self.key_file, cert_file=self.cert_file, timeout=self.timeout) #**(x509 or {}))
            conn = HTTPS(host, None, key_file=self.key_file, cert_file=self.cert_file) #**(x509 or {}))

        if hasattr(conn, 'set_timeout'):
            conn.set_timeout(self.timeout)

        # Some logic to deal with timeouts. It appears that some (or all) versions
        # of python don't set the timeout after the socket is created. We'll do it
        # ourselves by forcing the connection to connect, finding the socket, and
        # calling settimeout() on it. (tested with python 2.6)
        if self.timeout:
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
        self.url=url
        xmlrpclib.ServerProxy.__init__(self, url, transport, allow_none=allow_none, verbose=verbose)

    def __getattr__(self, attr):
        logger.debug ("xml-rpc %s method:%s"%(self.url,attr))
        return xmlrpclib.ServerProxy.__getattr__(self, attr)

def server_proxy(url, key_file, cert_file, timeout=None, verbose=False):
    transport = XMLRPCTransport(key_file, cert_file, timeout)
    return XMLRPCServerProxy(url, transport, allow_none=True, verbose=verbose)

