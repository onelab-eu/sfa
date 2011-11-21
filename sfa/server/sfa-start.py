#!/usr/bin/python
#
# PlanetLab SFA implementation
#
# This implements the SFA Registry and Slice Interfaces on PLC.
# Depending on command line options, it starts some combination of a
# Registry, an Aggregate Manager, and a Slice Manager.
#
# There are several items that need to be done before starting the servers.
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
#registry_port=12345
#aggregate_port=12346
#slicemgr_port=12347
### xxx todo not in the config yet
component_port=12346
import os, os.path
import traceback
import sys
from optparse import OptionParser

from sfa.util.sfalogging import logger
from sfa.util.xrn import get_authority, hrn_to_urn
from sfa.util.config import Config
import sfa.client.xmlrpcprotocol as xmlrpcprotocol
from sfa.trust.gid import GID
from sfa.trust.trustedroots import TrustedRoots
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.hierarchy import Hierarchy
from sfa.trust.gid import GID

from sfa.server.sfaapi import SfaApi

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
    logdir='/var/log/httpd'
    # when installed in standalone we might not have httpd installed
    if not os.path.isdir(logdir): os.mkdir('/var/log/httpd')
    crashlog = os.open('%s/sfa_access_log'%logdir, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0644)
    os.dup2(crashlog, 1)
    os.dup2(crashlog, 2)


def install_peer_certs(server_key_file, server_cert_file):
    """
    Attempt to install missing trusted gids and db records for 
    our federated interfaces
    """
    # Attempt to get any missing peer gids
    # There should be a gid file in /etc/sfa/trusted_roots for every
    # peer registry found in in the registries.xml config file. If there
    # are any missing gids, request a new one from the peer registry.
    api = SfaApi(key_file = server_key_file, cert_file = server_cert_file)
    registries = Registries()
    aggregates = Aggregates()
    interfaces = dict(registries.items() + aggregates.items())
    gids_current = api.auth.trusted_cert_list
    hrns_current = [gid.get_hrn() for gid in gids_current]
    hrns_expected = set([hrn for hrn in interfaces])
    new_hrns = set(hrns_expected).difference(hrns_current)
    #gids = self.get_peer_gids(new_hrns) + gids_current
    peer_gids = []
    if not new_hrns:
        return 

    trusted_certs_dir = api.config.get_trustedroots_dir()
    for new_hrn in new_hrns:
        if not new_hrn: continue
        # the gid for this interface should already be installed
        if new_hrn == api.config.SFA_INTERFACE_HRN: continue
        try:
            # get gid from the registry
            url = interfaces[new_hrn].get_url()
            interface = interfaces[new_hrn].server_proxy(server_key_file, server_cert_file, timeout=30)
            # skip non sfa aggregates
            server_version = api.get_cached_server_version(interface)
            if 'sfa' not in server_version:
                logger.info("get_trusted_certs: skipping non sfa aggregate: %s" % new_hrn)
                continue
      
            trusted_gids = interface.get_trusted_certs()
            if trusted_gids:
                # the gid we want should be the first one in the list,
                # but lets make sure
                for trusted_gid in trusted_gids:
                    # default message
                    message = "interface: %s\t" % (api.interface)
                    message += "unable to install trusted gid for %s" % \
                               (new_hrn)
                    gid = GID(string=trusted_gids[0])
                    peer_gids.append(gid)
                    if gid.get_hrn() == new_hrn:
                        gid_filename = os.path.join(trusted_certs_dir, '%s.gid' % new_hrn)
                        gid.save_to_file(gid_filename, save_parents=True)
                        message = "installed trusted cert for %s" % new_hrn
                    # log the message
                    api.logger.info(message)
        except:
            message = "interface: %s\tunable to install trusted gid for %s" % \
                        (api.interface, new_hrn)
            api.logger.log_exc(message)
    # doesnt matter witch one
    update_cert_records(peer_gids)

def update_cert_records(gids):
    """
    Make sure there is a record in the registry for the specified gids. 
    Removes old records from the db.
    """
    # import SfaTable here so this module can be loaded by PlcComponentApi
    from sfa.util.table import SfaTable
    from sfa.util.record import SfaRecord
    if not gids:
        return
    table = SfaTable()
    # get records that actually exist in the db
    gid_urns = [gid.get_urn() for gid in gids]
    hrns_expected = [gid.get_hrn() for gid in gids]
    records_found = table.find({'hrn': hrns_expected, 'pointer': -1}) 

    # remove old records
    for record in records_found:
        if record['hrn'] not in hrns_expected and \
            record['hrn'] != self.api.config.SFA_INTERFACE_HRN:
            table.remove(record)

    # TODO: store urn in the db so we do this in 1 query 
    for gid in gids:
        hrn, type = gid.get_hrn(), gid.get_type()
        record = table.find({'hrn': hrn, 'type': type, 'pointer': -1})
        if not record:
            record = {
                'hrn': hrn, 'type': type, 'pointer': -1,
                'authority': get_authority(hrn),
                'gid': gid.save_to_string(save_parents=True),
            }
            record = SfaRecord(dict=record)
            table.insert(record)
        
def main():
    # Generate command line parser
    parser = OptionParser(usage="sfa-start.py [options]")
    parser.add_option("-r", "--registry", dest="registry", action="store_true",
         help="run registry server", default=False)
    parser.add_option("-s", "--slicemgr", dest="sm", action="store_true",
         help="run slice manager", default=False)
    parser.add_option("-a", "--aggregate", dest="am", action="store_true",
         help="run aggregate manager", default=False)
    parser.add_option("-c", "--component", dest="cm", action="store_true",
         help="run component server", default=False)
    parser.add_option("-t", "--trusted-certs", dest="trusted_certs", action="store_true",
         help="refresh trusted certs", default=False)
    parser.add_option("-v", "--verbose", action="count", dest="verbose", default=0,
         help="verbose mode - cumulative")
    parser.add_option("-d", "--daemon", dest="daemon", action="store_true",
         help="Run as daemon.", default=False)
    (options, args) = parser.parse_args()
    
    config = Config()
    if config.SFA_API_DEBUG: pass

    # ge the server's key and cert
    hierarchy = Hierarchy()
    auth_info = hierarchy.get_interface_auth_info()
    server_key_file = auth_info.get_privkey_filename()
    server_cert_file = auth_info.get_gid_filename()

    # ensure interface cert is present in trusted roots dir
    trusted_roots = TrustedRoots(config.get_trustedroots_dir())
    trusted_roots.add_gid(GID(filename=server_cert_file))
    if (options.daemon):  daemon()
    
    if options.trusted_certs:
        install_peer_certs(server_key_file, server_cert_file)   
    
    # start registry server
    if (options.registry):
        from sfa.server.registry import Registry
        r = Registry("", config.SFA_REGISTRY_PORT, server_key_file, server_cert_file)
        r.start()

    if (options.am):
        from sfa.server.aggregate import Aggregate
        a = Aggregate("", config.SFA_AGGREGATE_PORT, server_key_file, server_cert_file)
        a.start()

    # start slice manager
    if (options.sm):
        from sfa.server.slicemgr import SliceMgr
        s = SliceMgr("", config.SFA_SM_PORT, server_key_file, server_cert_file)
        s.start()

    if (options.cm):
        from sfa.server.component import Component
        c = Component("", config.component_port, server_key_file, server_cert_file)
#        c = Component("", config.SFA_COMPONENT_PORT, server_key_file, server_cert_file)
        c.start()

if __name__ == "__main__":
    try:
        main()
    except:
        logger.log_exc_critical("SFA server is exiting")
