from ssl import SSLSocket

import textwrap

import _ssl             # if we can't import it, let the error propagate

from _ssl import SSLError
from _ssl import CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
from _ssl import PROTOCOL_SSLv2, PROTOCOL_SSLv3, PROTOCOL_SSLv23, PROTOCOL_TLSv1
from _ssl import RAND_status, RAND_egd, RAND_add
from _ssl import \
     SSL_ERROR_ZERO_RETURN, \
     SSL_ERROR_WANT_READ, \
     SSL_ERROR_WANT_WRITE, \
     SSL_ERROR_WANT_X509_LOOKUP, \
     SSL_ERROR_SYSCALL, \
     SSL_ERROR_SSL, \
     SSL_ERROR_WANT_CONNECT, \
     SSL_ERROR_EOF, \
     SSL_ERROR_INVALID_ERROR_CODE

from socket import socket, _fileobject
from socket import getnameinfo as _getnameinfo
import base64        # for DER-to-PEM translation

class SSLSocket(SSLSocket, socket):

    """This class implements a subtype of socket.socket that wraps
    the underlying OS socket in an SSL context when necessary, and
    provides read and write methods over that channel."""

    def __init__(self, sock, keyfile=None, certfile=None,
                 server_side=False, cert_reqs=CERT_NONE,
                 ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                 do_handshake_on_connect=True,
                 suppress_ragged_eofs=True):
        socket.__init__(self, _sock=sock._sock)
        # the initializer for socket trashes the methods (tsk, tsk), so...
        self.send = lambda data, flags=0: SSLSocket.send(self, data, flags)
        self.sendto = lambda data, addr, flags=0: SSLSocket.sendto(self, data, addr, flags)
        self.recv = lambda buflen=1024, flags=0: SSLSocket.recv(self, buflen, flags)
        self.recvfrom = lambda addr, buflen=1024, flags=0: SSLSocket.recvfrom(self, addr, buflen, flags)
        self.recv_into = lambda buffer, nbytes=None, flags=0: SSLSocket.recv_into(self, buffer, nbytes, flags)
        self.recvfrom_into = lambda buffer, nbytes=None, flags=0: SSLSocket.recvfrom_into(self, buffer, nbytes, flags)

        if certfile and not keyfile:
            keyfile = certfile
        # see if it's connected
        try:
            socket.getpeername(self)
        except:
            # no, no connection yet
            self._sslobj = None
        else:
            # yes, create the SSL object
            self._sslobj = _ssl.sslwrap(self._sock, server_side,
                                        keyfile, certfile,
                                        cert_reqs, ssl_version, ca_certs)
            if do_handshake_on_connect:
                timeout = self.gettimeout()
                try:
                    if timeout == 0:
                        self.settimeout(None)
                    self.do_handshake()
                finally:
                    self.settimeout(timeout)
        self.keyfile = keyfile
        self.certfile = certfile
        self.cert_reqs = cert_reqs
        self.ssl_version = ssl_version
        self.ca_certs = ca_certs
        self.do_handshake_on_connect = do_handshake_on_connect
        self.suppress_ragged_eofs = suppress_ragged_eofs
        self._makefile_refs = 0


