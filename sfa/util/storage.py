import os
from sfa.util.xml import XML

class SimpleStorage(dict):
    """
    Handles storing and loading python dictionaries. The storage file created
    is a string representation of the native python dictionary.
    """
    db_filename = None
    type = 'dict'
    
    def __init__(self, db_filename, db = {}):

        dict.__init__(self, db)
        self.db_filename = db_filename
    
    def load(self):
        if os.path.exists(self.db_filename) and os.path.isfile(self.db_filename):
            db_file = open(self.db_filename, 'r')
            dict.__init__(self, eval(db_file.read()))
        elif os.path.exists(self.db_filename) and not os.path.isfile(self.db_filename):
            raise IOError, '%s exists but is not a file. please remove it and try again' \
                           % self.db_filename
        else:
            self.write()
            self.load()
 
    def write(self):
        db_file = open(self.db_filename, 'w')  
        db_file.write(str(self))
        db_file.close()
    
    def sync(self):
        self.write()

class XmlStorage(SimpleStorage):
    """
    Handles storing and loading python dictionaries. The storage file created
    is a xml representation of the python dictionary.
    """ 
    db_filename = None
    type = 'xml'

    def load(self):
        """
        Parse an xml file and store it as a dict
        """ 
        if os.path.exists(self.db_filename) and os.path.isfile(self.db_filename):
            xml = XML(self.db_filename)
            dict.__init__(self, xml.todict())
        elif os.path.exists(self.db_filename) and not os.path.isfile(self.db_filename):
            raise IOError, '%s exists but is not a file. please remove it and try again' \
                           % self.db_filename
        else:
            self.write()
            self.load()

    def write(self):
        xml = XML()
        xml.parseDict(self)
        db_file = open(self.db_filename, 'w')
        db_file.write(data.toprettyxml())
        db_file.close()

    def sync(self):
        self.write()

                
