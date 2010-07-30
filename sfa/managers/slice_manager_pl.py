### $Id: slices.py 15842 2009-11-22 09:56:13Z anil $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/plc/slices.py $

import datetime
import time
import traceback
import sys
from copy import deepcopy
from lxml import etree
from StringIO import StringIO
from types import StringTypes
from sfa.util.rspec import merge_rspecs
from sfa.util.namespace import *
from sfa.util.rspec import *
from sfa.util.specdict import *
from sfa.util.faults import *
from sfa.util.record import SfaRecord
from sfa.util.policy import Policy
from sfa.util.prefixTree import prefixTree
from sfa.util.sfaticket import *
from sfa.util.threadmanager import ThreadManager
import sfa.util.xmlrpcprotocol as xmlrpcprotocol     
from sfa.util.debug import log
import sfa.plc.peers as peers

def delete_slice(api, xrn, origin_hrn=None):
    credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        server = api.aggregates[aggregate] 
        threads.run(server.delete_slice, credential, xrn, origin_hrn)
    threads.get_results()
    return 1

def create_slice(api, xrn, rspec, origin_hrn=None):
    hrn, type = urn_to_hrn(xrn)

    # Validate the RSpec against PlanetLab's schema --disabled for now
    # The schema used here needs to aggregate the PL and VINI schemas
    # schema = "/var/www/html/schemas/pl.rng"
    schema = None
    if schema:
        try:
            tree = etree.parse(StringIO(rspec))
        except etree.XMLSyntaxError:
            message = str(sys.exc_info()[1])
            raise InvalidRSpec(message)

        relaxng_doc = etree.parse(schema)
        relaxng = etree.RelaxNG(relaxng_doc)
        
        if not relaxng(tree):
            error = relaxng.error_log.last_error
            message = "%s (line %s)" % (error.message, error.line)
            raise InvalidRSpec(message)

    cred = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        if aggregate not in [api.auth.client_cred.get_gid_caller().get_hrn()]:
            server = api.aggregates[aggregate]
            # Just send entire RSpec to each aggregate
            threads.run(server.create_slice, cred, xrn, rspec, origin_hrn)
    threads.get_results() 
    return 1

def get_ticket(api, xrn, rspec, origin_hrn=None):
    slice_hrn, type = urn_to_hrn(xrn)
    # get the netspecs contained within the clients rspec
    aggregate_rspecs = {}
    tree= etree.parse(StringIO(rspec))
    elements = tree.findall('./network')
    for element in elements:
        aggregate_hrn = element.values()[0]
        aggregate_rspecs[aggregate_hrn] = rspec 

    # get a ticket from each aggregate 
    credential = api.getCredential()
    threads = ThreadManager()
    for aggregate, aggregate_rspec in aggregate_rspecs.items():
        server = None
        if aggregate in api.aggregates:
            server = api.aggregates[aggregate]
        else:
            net_urn = hrn_to_urn(aggregate, 'authority')     
            # we may have a peer that knows about this aggregate
            for agg in api.aggregates:
                agg_info = api.aggregates[agg].get_aggregates(credential, net_urn)
                if agg_info:
                    # send the request to this address 
                    url = 'http://%s:%s' % (agg_info['addr'], agg_info['port'])
                    server = xmlrpcprotocol.get_server(url, api.key_file, api.cert_file)
                    break   
        if server is None:
            continue 
        threads.run(server.get_ticket, credential, xrn, aggregate_rspec, origin_hrn)
    results = threads.get_results()
    
    # gather information from each ticket 
    rspecs = []
    initscripts = []
    slivers = [] 
    object_gid = None  
    for result in results:
        agg_ticket = SfaTicket(string=result)
        attrs = agg_ticket.get_attributes()
        if not object_gid:
            object_gid = agg_ticket.get_gid_object()
        print object_gid
        rspecs.append(agg_ticket.get_rspec())
        initscripts.extend(attrs.get('initscripts', [])) 
        slivers.extend(attrs.get('slivers', [])) 
    
    # merge info
    attributes = {'initscripts': initscripts,
                 'slivers': slivers}
    merged_rspec = merge_rspecs(rspecs) 

    # create a new ticket
    ticket = SfaTicket(subject = slice_hrn)
    ticket.set_gid_caller(api.auth.client_gid)
    ticket.set_issuer(key=api.key, subject=api.hrn)
    ticket.set_gid_object(object_gid)
    ticket.set_pubkey(object_gid.get_pubkey())
    #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
    ticket.set_attributes(attributes)
    ticket.set_rspec(merged_rspec)
    ticket.encode()
    ticket.sign()          
    return ticket.save_to_string(save_parents=True)

def start_slice(api, xrn):
    credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        server = api.aggregates[aggregate]
        threads.run(server.stop_slice, credential, xrn)
    threads.get_results()    
    return 1
 
def stop_slice(api, xrn):
    credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        server = api.aggregates[aggregate]
        threads.run(server.stop_slice, credential, xrn)
    threads.get_results()    
    return 1

def reset_slice(api, xrn):
    # XX not implemented at this interface
    return 1

def get_slices(api):
    # look in cache first
    if api.cache:
        slices = api.cache.get('slices')
        if slices:
            return slices    

    # fetch from aggregates
    slices = []
    credential = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        server = api.aggregates[aggregate]
        threads.run(server.get_slices, credential)

    # combime results
    results = threads.get_results()
    slices = []
    for result in results:
        slices.extend(result)
    
    # cache the result
    if api.cache:
        api.cache.add('slices', slices)

    return slices
 
def get_rspec(api, xrn=None, origin_hrn=None):
    # look in cache first 
    if api.cache and not xrn:
        rspec =  api.cache.get('nodes')
        if rspec:
            return rspec

    hrn, type = urn_to_hrn(xrn)
    rspec = None
    cred = api.getCredential()
    threads = ThreadManager()
    for aggregate in api.aggregates:
        if aggregate not in [api.auth.client_cred.get_gid_caller().get_hrn()]:      
            # get the rspec from the aggregate
            server = api.aggregates[aggregate]
            threads.run(server.get_resources, cred, xrn, origin_hrn)

    results = threads.get_results()
    # combine the rspecs into a single rspec 
    for agg_rspec in results:
        try:
            tree = etree.parse(StringIO(agg_rspec))
        except etree.XMLSyntaxError:
            message = str(agg_rspec) + ": " + str(sys.exc_info()[1])
            raise InvalidRSpec(message)

        root = tree.getroot()
        if root.get("type") in ["SFA"]:
            if rspec == None:
                rspec = root
            else:
                for network in root.iterfind("./network"):
                    rspec.append(deepcopy(network))
                for request in root.iterfind("./request"):
                    rspec.append(deepcopy(request))

    rspec =  etree.tostring(rspec, xml_declaration=True, pretty_print=True)
    # cache the result
    if api.cache and not xrn:
        api.cache.add('nodes', rspec)
 
    return rspec

"""
Returns the request context required by sfatables. At some point, this
mechanism should be changed to refer to "contexts", which is the
information that sfatables is requesting. But for now, we just return
the basic information needed in a dict.
"""
def fetch_context(slice_hrn, user_hrn, contexts):
    #slice_hrn = urn_to_hrn(slice_xrn)[0]
    #user_hrn = urn_to_hrn(user_xrn)[0]
    base_context = {'sfa':{'user':{'hrn':user_hrn}, 'slice':{'hrn':slice_hrn}}}
    return base_context

def main():
    r = RSpec()
    r.parseFile(sys.argv[1])
    rspec = r.toDict()
    create_slice(None,'plc.princeton.tmacktestslice',rspec)

if __name__ == "__main__":
    main()
    
