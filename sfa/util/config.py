##
# SFA Configuration Info
#
# This module holds configuration parameters for SFA. There are two
# main pieces of information that are used: the database connection and
# the PLCAPI connection
##

##
# SFA uses a MYSQL database to store records. This database may be
# co-located with the PLC database, or it may be a separate database. The
# following parameters define the connection to the database.
#
# Note that SFA does not access any of the PLC databases directly via
# a mysql connection; All PLC databases are accessed via PLCAPI.

import os.path
import traceback

class Config:
    """
    Parse the bash/Python/PHP version of the configuration file. Very
    fast but no type conversions.
    """

    def __init__(self, config_file = "/etc/sfa/sfa_config.py"):
        self.config_file = None
        self.config_path = None
        self.data_path = None
        self.load(config_file)

    def load(self, config_file):
        try:
            execfile(config_file, self.__dict__)
            self.config_file = config_file
            # path to configuration data
            self.config_path = os.path.dirname(config_file)
            
            ### xxx todo implement defaults in default_config.xml 
            # path to server data
            if not hasattr(self, 'SFA_DATA_DIR'):
                # default to /var/lib/sfa not specified in config
                self.SFA_DATA_DIR="/var/lib/sfa"
                self.data_path = self.SFA_DATA_DIR
            else:
                self.data_path = self.SFA_DATA_DIR
                
            # path to config data
            if not hasattr(self, 'SFA_CONFIG_DIR'):
                # default to /etc/sfa not specified in config
                self.SFA_CONFIG_DIR="/etc/sfa"

            if not hasattr(self, 'SFA_REGISTRY_LEVEL1_AUTH'):
                self.SFA_REGISTRY_LEVEL1_AUTH=None

            # create the data directory if it doesnt exist
            if not os.path.isdir(self.SFA_DATA_DIR):
                try:
                    os.mkdir(self.SFA_DATA_DIR)
                except: pass
             
        except IOError, e:
            raise IOError, "Could not find or load the configuration file: %s" % config_file

    def get_trustedroots_dir(self):
        return self.config_path + os.sep + 'trusted_roots'

    def get_openflow_aggrMgr_info(self):
        aggr_mgr_ip = 'localhost'
        if (hasattr(self,'OPENFLOW_AGGREGATE_MANAGER_IP')):
            aggr_mgr_ip = self.OPENFLOW_AGGREGATE_MANAGER_IP

        aggr_mgr_port = 2603
        if (hasattr(self,'OPENFLOW_AGGREGATE_MANAGER_PORT')):
            aggr_mgr_port = self.OPENFLOW_AGGREGATE_MANAGER_PORT

        return (aggr_mgr_ip,aggr_mgr_port)

    def get_interface_hrn(self):
        if (hasattr(self,'SFA_INTERFACE_HRN')):
            return self.SFA_INTERFACE_HRN
        else:
            return "plc"

    # TODO: find a better place to put this method
    def get_max_aggrMgr_info(self):
        am_apiclient_path = '/usr/local/MAXGENI_AM_APIClient'
        if (hasattr(self,'MAXGENI_AM_APICLIENT_PATH')):
            am_client_path = self.MAXGENI_AM_APICLIENT_PATH

        am_url = 'https://geni.dragon.maxgigapop.net:8443/axis2/services/AggregateGENI'
        if (hasattr(self,'MAXGENI_AM_URL')):
            am_url = self.MAXGENI_AM_URL

        return (am_apiclient_path,am_url)

