#!/usr/bin/env python

# this is designed to use a totally empty new directory
# so we demonstrate how to bootstrap the whole thing

# init logging on console
import logging
console = logging.StreamHandler()
logger=logging.getLogger('')
logger.addHandler(console)
logger.setLevel(logging.DEBUG)

import uuid
def unique_call_id(): return uuid.uuid4().urn

# use sys.argv to point to a completely fresh directory
import sys
args=sys.argv[1:]
if len(args)!=1:
    print "Usage: %s directory"%sys.argv[0]
    sys.exit(1)
dir=args[0]
logger.debug('sfaclientsample: Using directory %s'%dir)

###

# this uses a test sfa deployment at openlab
registry_url="http://sfa1.pl.sophia.inria.fr:12345/"
aggregate_url="http://sfa1.pl.sophia.inria.fr:12347/"
# this is where the private key sits - would be ~/.ssh/id_rsa in most cases
# but in this context, create this local file
# the tests key pair can be found in
# http://git.onelab.eu/?p=tests.git;a=blob;f=system/config_default.py
# search for public_key / private_key
private_key="miniclient-private-key"
# user hrn
user_hrn="pla.inri.fake-pi1"

slice_hrn="pla.inri.slpl1"
# hrn_to_urn(slice_hrn,'slice')
slice_urn='urn:publicid:IDN+pla:inri+slice+slpl1'

from sfa.client.sfaclientlib import SfaClientBootstrap

bootstrap = SfaClientBootstrap (user_hrn, registry_url, dir=dir, logger=logger)
# install the private key in the client directory from 'private_key'
bootstrap.init_private_key_if_missing(private_key)

def truncate(content, length=20, suffix='...'):
    if isinstance (content, (int) ): return content
    if isinstance (content, list): return truncate ( "%s"%content, length, suffix)
    if len(content) <= length:
        return content
    else:
        return content[:length+1]+ ' '+suffix

def has_call_id (server_version):
    return server_version.has_key('call_id_support')


### issue a GetVersion call
### this assumes we've already somehow initialized the certificate
def get_version (url):
    # make sure we have a self-signed cert
    bootstrap.self_signed_cert()
    server_proxy = bootstrap.server_proxy_simple(url)
    server_version = server_proxy.GetVersion()
    print "miniclient: GetVersion at %s returned:"%(url)
    for (k,v) in server_version.iteritems(): print "miniclient: \tversion[%s]=%s"%(k,truncate(v))
    print "has-call-id=",has_call_id(server_version)

# version_dict = {'type': 'SFA', 'version': '1', }

version_dict = {'type':'ProtoGENI', 'version':'2'}


# ditto with list resources
def list_resources ():
    bootstrap.bootstrap_my_gid()
    credential = bootstrap.my_credential_string()
    credentials = [ credential ]
    options = {}
    options [ 'geni_rspec_version' ] = version_dict
#    options [ 'call_id' ] = unique_call_id()
    list_resources = bootstrap.server_proxy (aggregate_url).ListResources(credentials,options)
    print "miniclient: ListResources at %s returned : %s"%(aggregate_url,truncate(list_resources))

def list_slice_resources ():
    bootstrap.bootstrap_my_gid()
    credential = bootstrap.slice_credential_string (slice_hrn)
    credentials = [ credential ]
    options = { }
    options [ 'geni_rspec_version' ] = version_dict
    options [ 'geni_slice_urn' ] = slice_urn
#    options [ 'call_id' ] = unique_call_id()
    list_resources = bootstrap.server_proxy (aggregate_url).ListResources(credentials,options)
    print "miniclient: ListResources at %s for slice %s returned : %s"%(aggregate_url,slice_urn,truncate(list_resources))
    
    
    

def main ():
    get_version(registry_url)
    get_version(aggregate_url)
#    list_resources()
#    list_slice_resources()

main()
