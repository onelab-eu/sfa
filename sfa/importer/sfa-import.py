#!/usr/bin/python

import sys

from optparse import OptionParser

from sfa.generic import Generic

from sfa.util.config import Config
from sfa.util.sfalogging import _SfaLogger

from sfa.trust.hierarchy import Hierarchy

from sfa.importer.sfaimporter import SfaImporter

COMMAND=sys.argv[0]

def main ():

    config = Config()
    logger = _SfaLogger(logfile='/var/log/sfa_import.log', loggername='importlog')
    logger.setLevelFromOptVerbose(config.SFA_API_LOGLEVEL)
    if not config.SFA_REGISTRY_ENABLED:
        logger.critical("COMMAND: need SFA_REGISTRY_ENABLED to run import")

    # testbed-neutral : create local certificates and the like
    auth_hierarchy = Hierarchy ()
    sfa_importer = SfaImporter(auth_hierarchy, logger)
    # testbed-specific
    testbed_importer = None
    generic=Generic.the_flavour()
    importer_class = generic.importer_class()
    if importer_class:
        logger.info ("Using flavour %s for importing (class %s)"%\
                         (generic.flavour,importer_class.__name__))
        testbed_importer = importer_class (auth_hierarchy, logger)

    parser = OptionParser ()
    sfa_importer.record_options (parser)
    if testbed_importer:
        testbed_importer.record_options (parser)

    (options, args) = parser.parse_args ()
    # no args supported ?
    if args:
        parser.print_help()
        sys.exit(1)

    sfa_importer.run (options)
    if testbed_importer:
        testbed_importer.run (parser)
    

if __name__ == '__main__':
    main()

