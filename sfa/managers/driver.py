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
    def is_enabled (self, record) : 
        return True

    # the following is used in Resolve (registry) when run in full mode
    #     after looking up the sfa db, we wish to be able to display
    #     testbed-specific info as well
    # this at minima should fill in the 'researcher' field for slice records
    # as this information is then used to compute rights
    # roadmap: there is an intention to redesign the SFA database so as to clear up 
    # this constraint, based on the principle that SFA should not rely on the
    # testbed database to perform such a core operation (i.e. getting rights right)
    def augment_records_with_testbed_info (self, sfa_records):
        return sfa_records

    # incoming record, as provided by the client to the Register API call
    # expected retcod 'pointer'
    # 'pointer' is typically an int db id, that makes sense in the testbed environment
    # -1 if this feature is not relevant 
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