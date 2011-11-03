#!/usr/bin/python

#
# SFA Certificate Signing and management. Root authorities can use this script 
# to sign  the certificate of another authority and become its parent. Sub 
# authorities (authorities that have had their cert signed by another authority) 
# can use this script to update their registry hierarchy with the new cert    
# 
# Example usage: 
#
## sign a peer cert
# sfa-ca.py --sign PEER_CERT_FILENAME -o OUTPUT_FILENAME 
#
## import a cert and update the registry hierarchy
# sfa-ca.py --import CERT_FILENAME   
#
## display a cert
# sfa-ca.py --display CERT_FILENAME


import os
import sys
from optparse import OptionParser

from sfa.util.config import Config
from sfa.util.table import SfaTable

from sfa.trust.gid import GID, create_uuid
from sfa.trust.hierarchy import Hierarchy

def main():
    args = sys.argv
    script_name = args[0]
    parser = OptionParser(usage="%(script_name)s [options]" % locals())
    parser.add_option("-d", "--display", dest="display", default=None,
                      help="print contents of specified gid")           
    parser.add_option("-s", "--sign", dest="sign", default=None, 
                      help="gid to sign" )
    parser.add_option("-k", "--key", dest="key", default=None, 
                      help="keyfile to use for signing")
    parser.add_option("-a", "--authority", dest="authority", default=None, 
                      help="sign the gid using the specified authority ")
    parser.add_option("-i", "--import", dest="importgid", default=None,
                      help="gid file to import into the registry")
    parser.add_option("-e", "--export", dest="export", 
                      help="name of gid to export from registry")
    parser.add_option("-t", "--type", dest="type",
                      help="record type", default=None)
    parser.add_option("-o", "--outfile", dest="outfile",
                      help="where to write the exprted gid") 
    parser.add_option("-v", "--verbose", dest="verbose", default=False, 
                      action="store_true", help="be verbose")           
                
    (options, args) = parser.parse_args()


    if options.display:
        display(options)
    elif options.sign:
        sign(options)
    elif options.importgid:
        import_gid(options) 
    elif options.export:
        export_gid(options)  
    else:
        parser.print_help()
        sys.exit(1)        


def display(options):
    """
    Display the sepcified GID
    """
    gidfile = os.path.abspath(options.display)
    if not gidfile or not os.path.isfile(gidfile):
        print "No such gid: %s" % gidfile
        sys.exit(1)
    gid = GID(filename=gidfile)
    gid.dump(dump_parents=True)

def sign(options):
    """
    Sign the specified gid
    """
    hierarchy = Hierarchy()
    config = Config()
    default_authority = config.SFA_INTERFACE_HRN
    auth_info = hierarchy.get_auth_info(default_authority)

    # load the gid
    gidfile = os.path.abspath(options.sign)
    if not os.path.isfile(gidfile):
        print "no such gid: %s" % gidfile
        sys.exit(1)
    gid = GID(filename=gidfile)

    # extract pub_key and create new gid
    pkey = gid.get_pubkey()
    urn = gid.get_urn()
    gid = hierarchy.create_gid(urn, create_uuid(), pkey)

    # get the outfile
    outfile = options.outfile
    if not outfile:
        outfile = os.path.abspath('./signed-%s.gid' % gid.get_hrn())
   
    # save the signed gid
    if options.verbose:
        print "Writing signed gid %s" % outfile  
    gid.save_to_file(outfile, save_parents=True)
    

def export_gid(options):
    # lookup the record for the specified hrn 
    hrn = options.export
    type = options.type
    # check sfa table first
    filter = {'hrn': hrn}
    if type:
        filter['type'] = type                    
    table = SfaTable()
    records = table.find(filter)
    if not records:
        # check the authorities hierarchy 
        hierarchy = Hierarchy()
        try:
            auth_info = hierarchy.get_auth_info(hrn)
            gid = auth_info.gid_object 
        except:
            print "Record: %s not found" % hrn
            sys.exit(1)
    else:
        record = records[0]
        gid = GID(string=record['gid'])
        
    # get the outfile
    outfile = options.outfile
    if not outfile:
        outfile = os.path.abspath('./%s.gid' % gid.get_hrn())

    # save it
    if options.verbose:
        print "Writing %s gid to %s" % (gid.get_hrn(), outfile)
    gid.save_to_file(outfile, save_parents=True)

def import_gid(options):
    """
    Import the specified gid into the registry (db and authorities 
    hierarchy) overwriting any previous gid.
    """
    # load the gid
    gidfile = os.path.abspath(options.importgid)
    if not gidfile or not os.path.isfile(gidfile):
        print "No such gid: %s" % gidfile
        sys.exit(1)
    gid = GID(filename=gidfile)
    
    # check if it exists within the hierarchy
    hierarchy = Hierarchy()
    if not hierarchy.auth_exists(gid.get_hrn()):
        print "%s not found in hierarchy" % gid.get_hrn()
        sys.exit(1)

    # check if record exists in db
    table = SfaTable()
    records = table.find({'hrn': gid.get_hrn(), 'type': 'authority'})
    if not records:
        print "%s not found in record database" % gid.get_hrn()  
        sys.exit(1)

    # update the database record
    record = records[0]
    record['gid'] = gid.save_to_string(save_parents=True)
    table.update(record)
    if options.verbose:
        print "Imported %s gid into db" % record['hrn']

    # update the hierarchy
    auth_info = hierarchy.get_auth_info(gid.get_hrn())  
    filename = auth_info.gid_filename
    gid.save_to_file(filename, save_parents=True)
    if options.verbose:
        print "Writing %s gid to %s" % (gid.get_hrn(), filename)

    # ending here
    return

if __name__ == '__main__':
    main()
