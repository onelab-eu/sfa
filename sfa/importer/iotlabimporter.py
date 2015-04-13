# -*- coding:utf-8 -*-
""" Iot-LAB importer class management """

from sfa.storage.alchemy import engine
from sfa.storage.model import init_tables
from sqlalchemy import Table, MetaData
from sqlalchemy.exc import NoSuchTableError

class IotLabImporter:
    """
    Creates the iotlab specific lease table to keep track
    of which slice hrn match OAR job
    """

    def __init__(self, auth_hierarchy, loc_logger):
        self.logger = loc_logger
        self.logger.setLevelDebug()

    def add_options (self, parser):
        """ Not used and need by SFA """
        pass
    
    def _exists(self, tablename):
        """
        Checks if the table exists in SFA database.
        """
        metadata = MetaData(bind=engine)
        try:
            Table(tablename, metadata, autoload=True)
            return True

        except NoSuchTableError:
            return False
     

    def run(self, options):
        """ Run importer"""
        if not self._exists('lease_table'):
            init_tables(engine)
            self.logger.info("iotlabimporter run lease_table created")
