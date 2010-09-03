#!/usr/bin/python
#
### $Id$
### $URL$
#
# SFA PLC Wrapper
#
# This wrapper implements the SFA Registry and Slice Interfaces on PLC.
# Depending on command line options, it starts some combination of a
# Registry, an Aggregate Manager, and a Slice Manager.
#
# There are several items that need to be done before starting the wrapper
# server.
#
# NOTE:  Many configuration settings, including the PLC maintenance account
# credentials, URI of the PLCAPI, and PLC DB URI and admin credentials are initialized
# from your MyPLC configuration (/etc/planetlab/plc_config*).  Please make sure this information
# is up to date and accurate.
#
# 1) Import the existing planetlab database, creating the
#    appropriate SFA records. This is done by running the "sfa-import-plc.py" tool.
#
# 2) Create a "trusted_roots" directory and place the certificate of the root
#    authority in that directory. Given the defaults in sfa-import-plc.py, this
#    certificate would be named "planetlab.gid". For example,
#
#    mkdir trusted_roots; cp authorities/planetlab.gid trusted_roots/
#
# TODO: Can all three servers use the same "registry" certificate?
##

# TCP ports for the three servers
registry_port=12345
aggregate_port=12346
slicemgr_port=12347
component_port=12346
import os, os.path
import sys
from optparse import OptionParser
from sfa.trust.trustedroot import TrustedRootList
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.hierarchy import Hierarchy
from sfa.util.config import Config
from sfa.util.report import trace
from sfa.plc.api import SfaAPI
from sfa.server.registry import Registries
from sfa.server.aggregate import Aggregates

# after http://www.erlenstar.demon.co.uk/unix/faq_2.html
def daemon():
    """Daemonize the current process."""
    if os.fork() != 0: os._exit(0)
    os.setsid()
    if os.fork() != 0: os._exit(0)
    os.umask(0)
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    # xxx fixme - this is just to make sure that nothing gets stupidly lost - should use devnull
    crashlog = os.open('/var/log/sfa.daemon', os.O_RDWR | os.O_APPEND | os.O_CREAT, 0644)
    os.dup2(crashlog, 1)
    os.dup2(crashlog, 2)

def init_server_key(server_key_file, server_cert_file, config, hierarchy):

    subject = config.SFA_INTERFACE_HRN
    # check if the server's private key exists. If it doesnt,
    # get the right one from the authorities directory. If it cant be
    # found in the authorities directory, generate a random one
    if not os.path.exists(server_key_file):
        hrn = config.SFA_INTERFACE_HRN.lower()
        hrn_parts = hrn.split(".")
        rel_key_path = hrn
        pkey_filename = hrn+".pkey"

        # sub authority's have "." in their hrn. This must
        # be converted to os.path separator
        if len(hrn_parts) > 0:
            rel_key_path = hrn.replace(".", os.sep)
            pkey_filename= hrn_parts[-1]+".pkey"

        key_file = os.sep.join([hierarchy.basedir, rel_key_path, pkey_filename])
        if not os.path.exists(key_file):
            # if it doesnt exist then this is probably a fresh interface
            # with no records. Generate a random keypair for now
            trace("server's public key not found in %s" % key_file)
            trace("generating a random server key pair")
            key = Keypair(create=True)
            key.save_to_file(server_key_file)
            cert = Certificate(subject=subject)
            cert.set_issuer(key=key, subject=subject)
            cert.set_pubkey(key)
            cert.sign()
            cert.save_to_file(server_cert_file, save_parents=True)

        else:
            # the pkey was found in the authorites directory. lets 
            # copy it to where the server key should be and generate
            # the cert
            key = Keypair(filename=key_file)
            key.save_to_file(server_key_file)
            cert = Certificate(subject=subject)
            cert.set_issuer(key=key, subject=subject)
            cert.set_pubkey(key)
            cert.sign()
            cert.save_to_file(server_cert_file, save_parents=True)


    # If private key exists and cert doesnt, recreate cert
    if (os.path.exists(server_key_file)) and (not os.path.exists(server_cert_file)):
        key = Keypair(filename=server_key_file)
        cert = Certificate(subject=subject)
        cert.set_issuer(key=key, subject=subject)
        cert.set_pubkey(key)
        cert.sign()
        cert.save_to_file(server_cert_file)

def init_server(options, config):
    """
    Execute the init method defined in the manager file 
    """
    manager_base = 'sfa.managers'
    if options.registry:
        mgr_type = config.SFA_REGISTRY_TYPE
        manager_module = manager_base + ".registry_manager_%s" % mgr_type
        try: manager = __import__(manager_module, fromlist=[manager_base])
        except: manager = None
        if manager and hasattr(manager, 'init_server'): 
            manager.init_server()    
    if options.am:
        mgr_type = config.SFA_AGGREGATE_TYPE
        manager_module = manager_base + ".aggregate_manager_%s" % mgr_type
        try: manager = __import__(manager_module, fromlist=[manager_base])
        except: manager = None
        if manager and hasattr(manager, 'init_server'):
            manager.init_server()    
    if options.sm:
        mgr_type = config.SFA_SM_TYPE
        manager_module = manager_base + ".slice_manager_%s" % mgr_type
        try: manager = __import__(manager_module, fromlist=[manager_base])
        except: manager = None
        if manager and hasattr(manager, 'init_server'):
            manager.init_server()    
    if options.cm:
        mgr_type = config.SFA_CM_TYPE
        manager_module = manager_base + ".component_manager_%s" % mgr_type
        try: manager = __import__(manager_module, fromlist=[manager_base])
        except: manager = None
        if manager and hasattr(manager, 'init_server'):
            manager.init_server()

def sync_interfaces(server_key_file, server_cert_file):
    """
    Attempt to install missing trusted gids and db records for 
    our federated interfaces
    """
    api = SfaAPI(key_file = server_key_file, cert_file = server_cert_file)
    registries = Registries(api)
    aggregates = Aggregates(api)
    registries.sync_interfaces()
    aggregates.sync_interfaces()

def main():
    # xxx get rid of globals - name consistently CamelCase or under_score
    global AuthHierarchy
    global TrustedRoots
    global registry_port
    global aggregate_port
    global slicemgr_port

    # Generate command line parser
    parser = OptionParser(usage="sfa-server [options]")
    parser.add_option("-r", "--registry", dest="registry", action="store_true",
         help="run registry server", default=False)
    parser.add_option("-s", "--slicemgr", dest="sm", action="store_true",
         help="run slice manager", default=False)
    parser.add_option("-a", "--aggregate", dest="am", action="store_true",
         help="run aggregate manager", default=False)
    parser.add_option("-c", "--component", dest="cm", action="store_true",
         help="run component server", default=False)
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true", 
         help="verbose mode", default=False)
    parser.add_option("-d", "--daemon", dest="daemon", action="store_true",
         help="Run as daemon.", default=False)
    (options, args) = parser.parse_args()


    config = Config()
    hierarchy = Hierarchy()
    server_key_file = os.path.join(hierarchy.basedir, "server.key")
    server_cert_file = os.path.join(hierarchy.basedir, "server.cert")

    init_server_key(server_key_file, server_cert_file, config, hierarchy)
    init_server(options, config)
    sync_interfaces(server_key_file, server_cert_file)   
 
    if (options.daemon):  daemon()
    # start registry server
    if (options.registry):
        from sfa.server.registry import Registry
        r = Registry("", registry_port, server_key_file, server_cert_file)
        r.start()

    # start aggregate manager
    if (options.am):
        from sfa.server.aggregate import Aggregate
        a = Aggregate("", aggregate_port, server_key_file, server_cert_file)
        a.start()

    # start slice manager
    if (options.sm):
        from sfa.server.slicemgr import SliceMgr
        s = SliceMgr("", slicemgr_port, server_key_file, server_cert_file)
        s.start()

    if (options.cm):
        from sfa.server.component import Component
        c = Component("", component_port, server_key_file, server_cert_file)
        c.start()

if __name__ == "__main__":
    main()
