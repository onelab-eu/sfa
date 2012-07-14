#!/usr/bin/python
import sys
import os
import ConfigParser
import tempfile
from sfa.util.xml import XML

default_config = \
"""
"""

class Config:
  
    def __init__(self, config_file='/etc/sfa/sfa_config'):
        self.config = ConfigParser.ConfigParser()  
        self.filename = config_file
        if not os.path.isfile(self.filename):
            self.create(self.filename)
        self.load(self.filename)

    def create(self, filename):
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        configfile = open(filename, 'w')
        configfile.write(default_config)
        configfile.close()
        

    def load(self, filename):
        if filename:
            if filename.endswith('.xml'):
                try:
                    self.load_xml(filename)
                except:
                    raise 
                    self.config.read(filename)
            else:
                self.config.read(filename)
        self.set_attributes()
                
    def load_xml(self, filename):
        xml = XML(filename)
        categories = xml.xpath('//configuration/variables/category')
        for category in categories:
            section_name = category.get('id')
            if not self.config.has_section(section_name):
                self.config.add_section(section_name)
            options = category.xpath('./variablelist/variable')
            for option in options:
                option_name = option.get('id')
                value = option.xpath('./value')[0].text
                if not value:
                    value = ""
                self.config.set(section_name, option_name, value)
         

    def locate_varname(self, varname):
        varname = varname.lower()
        sections = self.config.sections()
        section_name = ""
        var_name = ""
        for section in sections:
            if varname.startswith(section.lower()) and len(section) > len(section_name):
                section_name = section.lower()
                var_name = varname.replace(section_name, "")[1:]
        if not self.config.has_option(section_name, var_name):
            raise ConfigParser.NoOptionError(varname, section_name)
        return (section_name, var_name)             

    def set_attributes(self):
        sections = self.config.sections()
        for section in sections:
            for item in self.config.items(section):
                name = "%s_%s" % (section, item[0])
                value = item[1]
                setattr(self, name, value)
                setattr(self, name.upper(), value)
        

    def verify(self, config1, config2, validate_method):
        return True

    def validate_type(self, var_type, value):
        return True

    def dump(self, sections = []):
        if not sections:
            sections = self.config.sections() 
        print "" 
        for section in sections:
            print "[%s]" % section
            for item in self.config.items(section):
                print "%s=%s" % (item[0], item[1])
            print "" 
        
    def write(self, filename=None):
        if not filename:
            filename = self.filename
        configfile = open(filename, 'w') 
        self.config.write(configfile)
    
    def save(self, filename=None):
        self.write(filename)

    def __getattr__(self, attr):
        return getattr(self.config, attr)

if __name__ == '__main__':
    filename = None
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        config = Config(filename)
    else:    
        config = Config()
    config.dump()
    
