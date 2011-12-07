#!/usr/bin/env python

# this is designed to use a totally empty new directory
# so we demonstrate how to bootstrap the whole thing

# init logging on console
import logging
console = logging.StreamHandler()
logger=logging.getLogger('')
logger.addHandler(console)
logger.setLevel(logging.DEBUG)

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
hrn="pla.inri.fake-pi1"

from sfa.client.sfaclientlib import SfaClientBootstrap

bootstrap = SfaClientBootstrap (hrn, registry_url, dir=dir, logger=logger)
# install the private key in the client directory from 'private_key'
bootstrap.init_private_key_if_missing(private_key)
bootstrap.bootstrap_gid()

### issue a GetVersion call
### this assumes we've already somehow initialized the certificate
def get_version (url):
    
    server_proxy = bootstrap.server_proxy(url)
    retcod = server_proxy.GetVersion()
    print "GetVersion at %s returned following keys: %s"%(url,retcod.keys())


# version_dict = {'type': 'SFA', 'version': '1', }

version_dict = {'type':'ProtoGENI', 'version':'2'}

# ditto with list resources
def list_resources ():
    options = { 'geni_rspec_version' : version_dict}
    credential = bootstrap.get_credential_string()
    credentials = [ credential ]
    retcod = bootstrap.server_proxy (aggregate_url).ListResources(credentials,options)
    print "ListResources at %s returned : %20s..."%(aggregate_url,retcod)

def main ():
    get_version(registry_url)
    get_version(aggregate_url)
    list_resources()

main()
