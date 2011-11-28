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
    def is_enabled_entity (self, record) : 
        return True
    
    # incoming record, as provided by the client to the Register API call
    # expected retcod 'pointer'
    # 'pointer' is typically an int db id, that makes sense in the testbed environment
    # -1 if this feature is not relevant 
    # here type will be 'authority'
    def register (self, sfa_record, hrn, pub_key) : 
        return -1

    # incoming record is the existing sfa_record
    # expected retcod boolean, error message logged if result is False
    def remove (self, sfa_record): 
        return True

    # incoming are the sfa_record:
    # (*) old_sfa_record is what we have in the db for that hrn
    # (*) new_sfa_record is what was passed in the Update call
    # expected retcod boolean, error message logged if result is False
    # NOTE 1. about keys
    # this is confusing because a user may have several ssh keys in 
    # the planetlab database, but we need to pick one to generate its cert
    # so as much as in principle we should be able to use new_sfa_record['keys']
    # the manager code actually picks one (the first one), and it seems safer
    # to pass it along rather than depending on the driver code to do the same
    #
    # NOTE 2. about keys
    # when changing the ssh key through this method the gid gets changed too
    # should anything be passed back to the caller in this case ?
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key): 
        return True
