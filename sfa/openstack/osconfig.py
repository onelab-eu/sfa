import ConfigParser
from sfa.util.sfalogging import logger

class OSConfig:

    def __init__(self, config_file="/etc/sfa/network.ini"):
        self.config = ConfigParser.ConfigParser()
        self.load(config_file)

    def load(self, config_file):
        if config_file:
            try:
                self.config.read(config_file)
            except Exception, e:
                logger.error("The network configuration file is missing...")

    def get(self, section, key):
        value = self.config.get(section, key)
        return value

