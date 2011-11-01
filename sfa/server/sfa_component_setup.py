#!/usr/bin/python
import sys
import os
import tempfile
from optparse import OptionParser

from sfa.util.faults import ConnectionKeyGIDMismatch
from sfa.util.config import Config
import sfa.client.xmlrpcprotocol as xmlrpcprotocol
from sfa.util.plxrn import hrn_to_pl_slicename, slicename_to_hrn

from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential
from sfa.trust.gid import GID
from sfa.trust.hierarchy import Hierarchy

KEYDIR = "/var/lib/sfa/"
CONFDIR = "/etc/sfa/"

def handle_gid_mismatch_exception(f):
    def wrapper(*args, **kwds):
        try: return f(*args, **kwds)
        except ConnectionKeyGIDMismatch:
            # clean regen server keypair and try again
            print "cleaning keys and trying again"
            clean_key_cred()
            return f(args, kwds)

    return wrapper

def server_proxy(url=None, port=None, keyfile=None, certfile=None,verbose=False):
    """
    returns an xmlrpc connection to the service a the specified 
    address
    """
    if url:
        url_parts = url.split(":")
        if len(url_parts) >1:
            pass
        else:
            url = "http://%(url)s:%(port)s" % locals()
    else:
        # connect to registry by default
        config = Config()
        addr, port = config.SFA_REGISTRY_HOST, config.SFA_REGISTRY_PORT
        url = "http://%(addr)s:%(port)s" % locals()

    if verbose:
        print "Contacting registry at: %(url)s" % locals()

    server = xmlrpcprotocol.server_proxy(url, keyfile, certfile)
    return server    
    

def create_default_dirs():
    config = Config()
    hierarchy = Hierarchy()
    config_dir = config.config_path
    trusted_certs_dir = config.get_trustedroots_dir()
    authorities_dir = hierarchy.basedir
    all_dirs = [config_dir, trusted_certs_dir, authorities_dir]
    for dir in all_dirs:
        if not os.path.exists(dir):
            os.makedirs(dir)

def has_node_key():
    key_file = KEYDIR + os.sep + 'server.key'
    return os.path.exists(key_file) 

def clean_key_cred():
    """
    remove the existing keypair and cred  and generate new ones
    """
    files = ["server.key", "server.cert", "node.cred"]
    for f in files:
        filepath = KEYDIR + os.sep + f
        if os.path.isfile(filepath):
            os.unlink(f)
   
    # install the new key pair
    # get_credential will take care of generating the new keypair
    # and credential 
    get_credential()
    
             
def get_node_key(registry=None, verbose=False):
    # this call requires no authentication, 
    # so we can generate a random keypair here
    subject="component"
    (kfd, keyfile) = tempfile.mkstemp()
    (cfd, certfile) = tempfile.mkstemp()
    key = Keypair(create=True)
    key.save_to_file(keyfile)
    cert = Certificate(subject=subject)
    cert.set_issuer(key=key, subject=subject)
    cert.set_pubkey(key)
    cert.sign()
    cert.save_to_file(certfile)
    
    registry = server_proxy(url = registry, keyfile=keyfile, certfile=certfile)    
    registry.get_key()

def create_server_keypair(keyfile=None, certfile=None, hrn="component", verbose=False):
    """
    create the server key/cert pair in the right place
    """
    key = Keypair(filename=keyfile)
    key.save_to_file(keyfile)
    cert = Certificate(subject=hrn)
    cert.set_issuer(key=key, subject=hrn)
    cert.set_pubkey(key)
    cert.sign()
    cert.save_to_file(certfile, save_parents=True)       

@handle_gid_mismatch_exception
def get_credential(registry=None, force=False, verbose=False):
    config = Config()
    hierarchy = Hierarchy()
    key_dir= hierarchy.basedir
    data_dir = config.data_path
    config_dir = config.config_path
    credfile = data_dir + os.sep + 'node.cred'
    # check for existing credential
    if not force and os.path.exists(credfile):
        if verbose:
            print "Loading Credential from %(credfile)s " % locals()  
        cred = Credential(filename=credfile).save_to_string(save_parents=True)
    else:
        if verbose:
            print "Getting credential from registry" 
        # make sure node private key exists
        node_pkey_file = config_dir + os.sep + "node.key"
        node_gid_file = config_dir + os.sep + "node.gid"
        if not os.path.exists(node_pkey_file) or \
           not os.path.exists(node_gid_file):
            get_node_key(registry=registry, verbose=verbose)
        
        gid = GID(filename=node_gid_file)
        hrn = gid.get_hrn()
        # create server key and certificate
        keyfile =data_dir + os.sep + "server.key"
        certfile = data_dir + os.sep + "server.cert"
        key = Keypair(filename=node_pkey_file)
        key.save_to_file(keyfile)
        create_server_keypair(keyfile, certfile, hrn, verbose)

        # get credential from registry 
        registry = server_proxy(url=registry, keyfile=keyfile, certfile=certfile)
        cert = Certificate(filename=certfile)
        cert_str = cert.save_to_string(save_parents=True)
        cred = registry.GetSelfCredential(cert_str, 'node', hrn)
        Credential(string=cred).save_to_file(credfile, save_parents=True)
    
    return cred

@handle_gid_mismatch_exception
def get_trusted_certs(registry=None, verbose=False):
    """
    refresh our list of trusted certs.
    """
    # define useful variables
    config = Config()
    data_dir = config.SFA_DATA_DIR
    config_dir = config.SFA_CONFIG_DIR
    trusted_certs_dir = config.get_trustedroots_dir()
    keyfile = data_dir + os.sep + "server.key"
    certfile = data_dir + os.sep + "server.cert"
    node_gid_file = config_dir + os.sep + "node.gid"
    node_gid = GID(filename=node_gid_file)
    hrn = node_gid.get_hrn()
    # get credential
    cred = get_credential(registry=registry, verbose=verbose)
    # make sure server key cert pair exists
    create_server_keypair(keyfile=keyfile, certfile=certfile, hrn=hrn, verbose=verbose)
    registry = server_proxy(url=registry, keyfile=keyfile, certfile=certfile)
    # get the trusted certs and save them in the right place
    if verbose:
        print "Getting trusted certs from registry"
    trusted_certs = registry.get_trusted_certs(cred)
    trusted_gid_names = [] 
    for gid_str in trusted_certs:
        gid = GID(string=gid_str)
        gid.decode()
        relative_filename = gid.get_hrn() + ".gid"
        trusted_gid_names.append(relative_filename)
        gid_filename = trusted_certs_dir + os.sep + relative_filename
        if verbose:
            print "Writing GID for %s as %s" % (gid.get_hrn(), gid_filename) 
        gid.save_to_file(gid_filename, save_parents=True)

    # remove old certs
    all_gids_names = os.listdir(trusted_certs_dir)
    for gid_name in all_gids_names:
        if gid_name not in trusted_gid_names:
            if verbose:
                print "Removing old gid ", gid_name
            os.unlink(trusted_certs_dir + os.sep + gid_name)                     

@handle_gid_mismatch_exception
def get_gids(registry=None, verbose=False):
    """
    Get the gid for all instantiated slices on this node and store it
    in /etc/sfa/slice.gid in the slice's filesystem
    """
    # define useful variables
    config = Config()
    data_dir = config.data_path
    config_dir = config.SFA_CONFIG_DIR
    trusted_certs_dir = config.get_trustedroots_dir()
    keyfile = data_dir + os.sep + "server.key"
    certfile = data_dir + os.sep + "server.cert"
    node_gid_file = config_dir + os.sep + "node.gid"
    node_gid = GID(filename=node_gid_file)
    hrn = node_gid.get_hrn()
    interface_hrn = config.SFA_INTERFACE_HRN
    # get credential
    cred = get_credential(registry=registry, verbose=verbose)
    # make sure server key cert pair exists
    create_server_keypair(keyfile=keyfile, certfile=certfile, hrn=hrn, verbose=verbose)
    registry = server_proxy(url=registry, keyfile=keyfile, certfile=certfile)
            
    if verbose:
        print "Getting current slices on this node"
    # get a list of slices on this node
    # make sure you run with SFA_GENERIC_FLAVOUR=plcm 
    from sfa.generic import Generic
    generic=Generic.the_flavour()
    api = generic.make_api(interface='component')
    xids_tuple = api.driver.nodemanager.GetXIDs()
    slices = eval(xids_tuple[1])
    slicenames = slices.keys()

    # generate a list of slices that dont have gids installed
    slices_without_gids = []
    for slicename in slicenames:
        if not os.path.isfile("/vservers/%s/etc/slice.gid" % slicename) \
        or not os.path.isfile("/vservers/%s/etc/node.gid" % slicename):
            slices_without_gids.append(slicename) 
    
    # convert slicenames to hrns
    hrns = [slicename_to_hrn(interface_hrn, slicename) \
            for slicename in slices_without_gids]
    
    # exit if there are no gids to install
    if not hrns:
        return
        
    if verbose:
        print "Getting gids for slices on this node from registry"  
    # get the gids
    # and save them in the right palce
    records = registry.GetGids(hrns, cred)
    for record in records:
        # if this isnt a slice record skip it
        if not record['type'] == 'slice':
            continue
        slicename = hrn_to_pl_slicename(record['hrn'])
        # if this slice isnt really instatiated skip it
        if not os.path.exists("/vservers/%(slicename)s" % locals()):
            continue
       
        # save the slice gid in /etc/sfa/ in the vservers filesystem
        vserver_path = "/vservers/%(slicename)s" % locals()
        gid = record['gid']
        slice_gid_filename = os.sep.join([vserver_path, "etc", "slice.gid"])
        if verbose:
            print "Saving GID for %(slicename)s as %(slice_gid_filename)s" % locals()
        GID(string=gid).save_to_file(slice_gid_filename, save_parents=True)
        # save the node gid in /etc/sfa
        node_gid_filename = os.sep.join([vserver_path, "etc", "node.gid"])
        if verbose:
            print "Saving node GID for %(slicename)s as %(node_gid_filename)s" % locals()
        node_gid.save_to_file(node_gid_filename, save_parents=True) 
                

def dispatch(options, args):

    create_default_dirs()
    if options.key:
        if options.verbose:
            print "Getting the component's pkey"
        get_node_key(registry=options.registry, verbose=options.verbose)
    if options.certs:
        if options.verbose:
            print "Getting the component's trusted certs"
        get_trusted_certs(verbose=options.verbose)
    if options.gids:        
        if options.verbose:
            print "Geting the component's GIDs"
        get_gids(verbose=options.verbose)

def main():
    args = sys.argv
    prog_name = args[0]
    parser = OptionParser(usage="%(prog_name)s [options]" % locals())
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
                      default=False, help="Be verbose") 
    parser.add_option("-r", "--registry", dest="registry", default=None,
                      help="Url of registry to contact")  
    parser.add_option("-k", "--key", dest="key", action="store_true", 
                     default=False,  
                     help="Get the node's pkey from the registry")
    parser.add_option("-c", "--certs", dest="certs", action="store_true",
                      default=False,
                      help="Get the trusted certs from the registry")
    parser.add_option("-g", "--gids", dest="gids", action="store_true",       
                      default=False,
                      help="Get gids for all the slices on the component")

    (options, args) = parser.parse_args()

    dispatch(options, args)

if __name__ == '__main__':
    main()    
