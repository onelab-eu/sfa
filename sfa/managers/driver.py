# 
# an attempt to document what a driver class should provide, 
# and implement reasonable defaults
#

class Driver:
    
    def __init__ (self): pass

    # redefine this if you want to check again records 
    # when running GetCredential
    # This is to reflect the 'enabled' user field in planetlab testbeds
    # expected retcod boolean
    def is_enabled_entity (self, record, aggregates) : return True
    
    # incoming record, as provided by the client to the Register API call
    # expected retcod 'pointer'
    # 'pointer' is typically an int db id, that makes sense in the testbed environment
    # -1 if this feature is not relevant 
    # here type will be 'authority'
    def register (self, hrn, sfa_record, pub_key) : return -1

    # incoming record is the existing sfa_record
    # no retcod expected for now
    def remove (self, sfa_record): return None
