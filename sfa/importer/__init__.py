#!/usr/bin/python

import sys
from datetime import datetime

from sfa.util.xrn import get_authority, hrn_to_urn
from sfa.generic import Generic
from sfa.util.config import Config
from sfa.util.sfalogging import _SfaLogger
from sfa.trust.hierarchy import Hierarchy
#from sfa.trust.trustedroots import TrustedRoots
from sfa.trust.gid import create_uuid
# using global alchemy.session() here is fine 
# as importer is on standalone one-shot process
from sfa.storage.alchemy import global_dbsession
from sfa.storage.model import RegRecord, RegAuthority, RegUser
from sfa.trust.certificate import convert_public_key, Keypair


class Importer:

    def __init__(self,auth_hierarchy=None,logger=None):
        self.config = Config()
        if auth_hierarchy is not None:
            self.auth_hierarchy=auth_hierarchy
        else:
            self.auth_hierarchy = Hierarchy ()
        if logger is not None:
            self.logger=logger
        else:
            self.logger = _SfaLogger(logfile='/var/log/sfa_import.log', loggername='importlog')
            self.logger.setLevelFromOptVerbose(self.config.SFA_API_LOGLEVEL)
# ugly side effect so that other modules get it right
        import sfa.util.sfalogging
        sfa.util.sfalogging.logger=logger
#        self.TrustedRoots = TrustedRoots(self.config.get_trustedroots_dir())    
   
    # check before creating a RegRecord entry as we run this over and over
    def record_exists (self, type, hrn):
       return global_dbsession.query(RegRecord).filter_by(hrn=hrn,type=type).count()!=0 

    def create_top_level_auth_records(self, hrn):
        """
        Create top level db records (includes root and sub authorities (local/remote)
        """
        # make sure parent exists
        parent_hrn = get_authority(hrn)
        if not parent_hrn:
            parent_hrn = hrn
        if not parent_hrn == hrn:
            self.create_top_level_auth_records(parent_hrn)

        # ensure key and cert exists:
        self.auth_hierarchy.create_top_level_auth(hrn)
        # create the db record if it doesnt already exist
        if not self.record_exists ('authority',hrn):
            auth_info = self.auth_hierarchy.get_auth_info(hrn)
            auth_record = RegAuthority(hrn=hrn, gid=auth_info.get_gid_object(),
                                       authority=get_authority(hrn))
            auth_record.just_created()
            global_dbsession.add (auth_record)
            global_dbsession.commit()
            self.logger.info("SfaImporter: imported authority (parent) %s " % auth_record)     
   

    def create_sm_client_record(self):
        """
        Create a user record for the Slicemanager service.
        """
        hrn = self.interface_hrn + '.slicemanager'
        urn = hrn_to_urn(hrn, 'user')
        if not self.auth_hierarchy.auth_exists(urn):
            self.logger.info("SfaImporter: creating Slice Manager user")
            self.auth_hierarchy.create_auth(urn)

        if self.record_exists ('user',hrn): return
        auth_info = self.auth_hierarchy.get_auth_info(hrn)
        user_record = RegUser(hrn=hrn, gid=auth_info.get_gid_object(),
                              authority=get_authority(hrn))
        user_record.just_created()
        global_dbsession.add (user_record)
        global_dbsession.commit()
        self.logger.info("SfaImporter: importing user (slicemanager) %s " % user_record)


    def create_interface_records(self):
        """
        Create a record for each SFA interface
        """
        # just create certs for all sfa interfaces even if they
        # aren't enabled
        auth_info = self.auth_hierarchy.get_auth_info(self.config.SFA_INTERFACE_HRN)
        pkey = auth_info.get_pkey_object()
        hrn=self.config.SFA_INTERFACE_HRN
        for type in  [ 'authority+sa', 'authority+am', 'authority+sm', ]:
            urn = hrn_to_urn(hrn, type)
            gid = self.auth_hierarchy.create_gid(urn, create_uuid(), pkey)
            # for now we have to preserve the authority+<> stuff
            if self.record_exists (type,hrn): continue
            interface_record = RegAuthority(type=type, hrn=hrn, gid=gid,
                                            authority=get_authority(hrn))
            interface_record.just_created()
            global_dbsession.add (interface_record)
            global_dbsession.commit()
            self.logger.info("SfaImporter: imported authority (%s) %s " % (type,interface_record))
 
    def run(self, options=None):
        if not self.config.SFA_REGISTRY_ENABLED:
            self.logger.critical("Importer: need SFA_REGISTRY_ENABLED to run import")

        # testbed-neutral : create local certificates and the like
        auth_hierarchy = Hierarchy ()
        self.create_top_level_auth_records(self.config.SFA_INTERFACE_HRN)
        self.create_interface_records()
 
        # testbed-specific
        testbed_importer = None
        generic=Generic.the_flavour()
        importer_class = generic.importer_class()
        if importer_class:
            begin_time=datetime.utcnow()
            self.logger.info (30*'=')
            self.logger.info ("Starting import on %s, using class %s from flavour %s"%\
                         (begin_time,importer_class.__name__,generic.flavour))
            testbed_importer = importer_class (auth_hierarchy, self.logger)
            if testbed_importer:
                testbed_importer.add_options(options)
                testbed_importer.run (options)
            end_time=datetime.utcnow()
            duration=end_time-begin_time
            self.logger.info("Import took %s"%duration)
            self.logger.info (30*'=')
