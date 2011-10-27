import sys

import socket
import struct

#The following is not essential
#from soaplib.wsgi_soap import SimpleWSGISoapApp
#from soaplib.serializers.primitive import *
#from soaplib.serializers.clazz import *

from sfa.util.faults import *
from sfa.util.xrn import urn_to_hrn
from sfa.server.registry import Registries
from sfa.util.config import Config
from sfa.plc.nodes import *
from sfa.util.callids import Callids

# Message IDs for all the SFA light calls
# This will be used by the aggrMgr controller
SFA_GET_RESOURCES = 101
SFA_CREATE_SLICE = 102
SFA_START_SLICE = 103
SFA_STOP_SLICE = 104
SFA_DELETE_SLICE = 105
SFA_GET_SLICES = 106
SFA_RESET_SLICES = 107

DEBUG = 1

def print_buffer(buf):
    for i in range(0,len(buf)):
        print('%x' % buf[i])

def extract(sock):
    # Shud we first obtain the message length?
    # msg_len = socket.ntohs(sock.recv(2))
    msg = ""

    while (1):
        try:
            chunk = sock.recv(1)
        except socket.error, message:
            if 'timed out' in message:
                break
            else:
                sys.exit("Socket error: " + message)

        if len(chunk) == 0:
            break
        msg += chunk

    print 'Done extracting %d bytes of response from aggrMgr' % len(msg)
    return msg
   
def connect(server, port):
    '''Connect to the Aggregate Manager module'''
    sock = socket.socket ( socket.AF_INET, socket.SOCK_STREAM )
    sock.connect ( ( server, port) )
    sock.settimeout(1)
    if DEBUG: print 'Connected!'
    return sock
    
def connect_aggrMgr():
    (aggr_mgr_ip, aggr_mgr_port) = Config().get_openflow_aggrMgr_info()
    if DEBUG: print """Connecting to port %d of %s""" % (aggr_mgr_port, aggr_mgr_ip)
    return connect(aggr_mgr_ip, aggr_mgr_port)

def generate_slide_id(cred, hrn):
    if cred == None:
        cred = ""
    if hrn == None:
        hrn = ""
    #return cred + '_' + hrn
    return str(hrn)

def msg_aggrMgr(cred, hrn, msg_id):
    slice_id = generate_slide_id(cred, hrn)

    msg = struct.pack('> B%ds' % len(slice_id), msg_id, slice_id)
    buf = struct.pack('> H', len(msg)+2) + msg

    try:
        aggrMgr_sock = connect_aggrMgr()
        aggrMgr_sock.send(buf)
        aggrMgr_sock.close()
        return 1
    except socket.error, message:
        print "Socket error"
    except IOerror, message:
        print "IO error"
    return 0

def start_slice(cred, xrn):
    hrn = urn_to_hrn(xrn)[0]
    if DEBUG: print "Received start_slice call"
    return msg_aggrMgr(SFA_START_SLICE)

def stop_slice(cred, xrn):
    hrn = urn_to_hrn(xrn)[0]
    if DEBUG: print "Received stop_slice call"
    return msg_aggrMgr(SFA_STOP_SLICE)

def DeleteSliver(cred, xrn, call_id):
    if Callids().already_handled(call_id): return ""
    hrn = urn_to_hrn(xrn)[0]
    if DEBUG: print "Received DeleteSliver call"
    return msg_aggrMgr(SFA_DELETE_SLICE)

def reset_slices(cred, xrn):
    hrn = urn_to_hrn(xrn)[0]
    if DEBUG: print "Received reset_slices call"
    return msg_aggrMgr(SFA_RESET_SLICES)

### Thierry: xxx this should ahve api as a first arg - probably outdated 
def CreateSliver(cred, xrn, rspec, call_id):
    if Callids().already_handled(call_id): return ""

    hrn = urn_to_hrn(xrn)[0]
    if DEBUG: print "Received CreateSliver call"
    slice_id = generate_slide_id(cred, hrn)

    msg = struct.pack('> B%ds%ds' % (len(slice_id)+1, len(rspec)), SFA_CREATE_SLICE, slice_id, rspec)
    buf = struct.pack('> H', len(msg)+2) + msg

    try:
        aggrMgr_sock = connect_aggrMgr()
        aggrMgr_sock.send(buf)
        if DEBUG: print "Sent %d bytes and closing connection" % len(buf)
        aggrMgr_sock.close()

        if DEBUG: print "----------------"
        return rspec
    except socket.error, message:
        print "Socket error"
    except IOerror, message:
        print "IO error"
    return ""

# Thierry : xxx this would need to handle call_id like the other AMs but is outdated...
def ListResources(cred, xrn=None):
    hrn = urn_to_hrn(xrn)[0]
    if DEBUG: print "Received ListResources call"
    slice_id = generate_slide_id(cred, hrn)

    msg = struct.pack('> B%ds' % len(slice_id), SFA_GET_RESOURCES, slice_id)
    buf = struct.pack('> H', len(msg)+2) + msg

    try:
        aggrMgr_sock = connect_aggrMgr()
        aggrMgr_sock.send(buf)
        resource_list = extract(aggrMgr_sock);
        aggrMgr_sock.close()

        if DEBUG: print "----------------"
        return resource_list 
    except socket.error, message:
        print "Socket error"
    except IOerror, message:
        print "IO error"
    return None

"""
Returns the request context required by sfatables. At some point, this mechanism should be changed
to refer to "contexts", which is the information that sfatables is requesting. But for now, we just
return the basic information needed in a dict.
"""
def fetch_context(slice_hrn, user_hrn, contexts):
    base_context = {'sfa':{'user':{'hrn':user_hrn}}}
    return base_context

def main():
    r = RSpec()
    r.parseFile(sys.argv[1])
    rspec = r.toDict()
    CreateSliver(None,'plc',rspec,'call-id-plc')
    
if __name__ == "__main__":
    main()
