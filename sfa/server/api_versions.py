import os
from sfa.util.xml import XML
from sfa.util.config import Config

class ApiVersions:

    required_fields = ['version', 'url']
    
    template = """<api_versions>
<api_version name="" version="" url="" />
</api_versions>""" 

    def __init__(self, string=None, filename=None, create=False):
        self.xml = None

        if create:
            self.create()
        elif string:
            self.load(string)
        elif filename:
            self.load(filename)
        else:
            # load the default file
            c = Config()
            api_versions_file = os.path.sep.join([c.config_path, 'api_versions.xml'])
            self.load(api_versions_file)
        
    def create(self):
        self.xml = XML(string=ApiVersions.template)

    def load(self, source):
        self.xml = XML(source)

    def get_versions(self):
        versions = {}
        for value in self.xml.todict().values():
            if not value:
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and \
                       set(ApiVersions.required_fields).issubset(item.keys()) and \
                       item['version'] != '' and item['url'] != '':
                        versions[str(item['version'])] = item['url']
        return versions  
                
           
