# 
# an attempt to document what a driver class should provide, 
# and implement reasonable defaults
#

class Driver:
    
    def __init__ (self, config): 
        # this is the hrn attached to the running server
        self.hrn = config.SFA_INTERFACE_HRN

    ########################################
    ########## registry oriented
    ########################################

    # NOTE: the is_enabled method is deprecated
    # it was only making things confusing, as the (PL) import mechanism would
    # ignore not enabled users anyway..

    # the following is used in Resolve (registry) when run in full mode
    #     after looking up the sfa db, we wish to be able to display
    #     testbed-specific info as well
    # based on the principle that SFA should not rely on the testbed database
    # to perform such a core operation (i.e. getting rights right) 
    # this is no longer in use when performing other SFA operations 
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

    # callack for register/update
    # this allows to capture changes in the relations between objects
    # the ids below are the ones found in the 'pointer' field
    # this can get typically called with
    # 'slice' 'user' 'researcher' slice_id user_ids 
    # 'authority' 'user' 'pi' authority_id user_ids 
    def update_relation (self, subject_type, target_type, relation_name, subject_id, link_ids):
        pass

    ########################################
    ########## aggregate oriented
    ########################################
    
    # a name for identifying the kind of testbed
    def testbed_name (self): return "undefined"

    # a dictionary that gets appended to the generic answer to GetVersion
    # 'geni_request_rspec_versions' and 'geni_ad_rspec_versions' are mandatory
    def aggregate_version (self): return {}

    # the answer to ListSlices, a list of slice urns
    def list_slices (self, creds, options):
        return []

    # answer to ListResources
    # first 2 args are None in case of resource discovery
    # expected : rspec (xml string)
    def list_resources (self, slice_urn, slice_hrn, creds, options):
        return "dummy Driver.list_resources needs to be redefined"

    # the answer to SliverStatus on a given slice
    def sliver_status (self, slice_urn, slice_hrn): return {}

    # the answer to CreateSliver on a given slice
    # expected to return a valid rspec 
    # identical to ListResources after the slice was modified
    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):
        return "dummy Driver.create_sliver needs to be redefined"

    # the answer to DeleteSliver on a given slice
    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        return "dummy Driver.delete_sliver needs to be redefined"

    # the answer to RenewSliver
    # expected to return a boolean to indicate success
    def renew_sliver (self, slice_urn, slice_hrn, creds, expiration_time, options):
        return False

    # the answer to start_slice/stop_slice
    # 1 means success, otherwise raise exception
    def start_slice (self, slice_urn, slice_xrn, creds):
        return 1
    def stop_slice (self, slice_urn, slice_xrn, creds):
        return 1
    # somehow this one does not have creds - not implemented in PL anyways
    def reset_slice (self, slice_urn, slice_xrn, creds):
        return 1

    # the answer to GetTicket
    # expected is a ticket, i.e. a certificate, as a string
    def get_ticket (self, slice_urn, slice_xrn, creds, rspec, options):
        return "dummy Driver.get_ticket needs to be redefined"

