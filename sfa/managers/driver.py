# 
# an attempt to document what a driver class should provide, 
# and implement reasonable defaults
#

class Driver:
    
    def __init__ (self, api): 
        self.api = api
        # this is the hrn attached to the running server
        self.hrn = api.config.SFA_INTERFACE_HRN

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

    # answer to ListResources
    # returns : advertisment rspec (xml string)
    def list_resources (self, version=None, options=None):
        if options is None: options={}
        return "dummy Driver.list_resources needs to be redefined"

    # the answer to Describe on a slice or a set of the slivers in a slice
    # returns: a struct:
    #{
    #  geni_rspec: <geni.rspec, a Manifest RSpec>
    #  geni_urn: <string slice urn of the containing slice>
    #  geni_slivers: [
    #              {
    #                geni_sliver_urn: <string sliver urn>
    #                geni_expires: <dateTime.rfc3339 allocation expiration string, as in geni_expires from SliversStatus>,
    #                geni_allocation_status: <string sliver state - e.g. geni_allocated or geni_provisioned >,
    #                geni_operational_status: <string sliver operational state>,
    #                geni_error: <optional string. The field may be omitted entirely but may not be null/None, explaining any failure for a sliver.>
    #              },
    #              ...
    #                ]
    #}
    def describe (self, urns, version, options=None):
        if options is None: options={}
        return "dummy Driver.describe needs to be redefined"

    # the answer to Allocate on a given slicei or a set of the slivers in a slice
    # returns: same struct as for describe.
    def allocate (self, urn, rspec_string, expiration, options=None):
        if options is None: options={}
        return "dummy Driver.allocate needs to be redefined"

    # the answer to Provision on a given slice or a set of the slivers in a slice
    # returns: same struct as for describe.
    def provision(self, urns, options=None):
        if options is None: options={}
        return "dummy Driver.provision needs to be redefined"

    # the answer to PerformOperationalAction on a given slice or a set of the slivers in a slice
    # returns: struct containing "geni_slivers" list of the struct returned by describe.
    def perform_operational_action (self, urns, action, options=None):
        if options is None: options={}
        return "dummy Driver.perform_operational_action needs to be redefined"

    # the answer to Status on a given slice or a set of the slivers in a slice
    # returns: struct containing "geni_urn" and "geni_slivers" list of the struct returned by describe.
    def status (self, urns, options=None): 
        if options is None: options={}
        return "dummy Driver.status needs to be redefined"

    # the answer to Renew on a given slice or a set of the slivers in a slice
    # returns: struct containing "geni_slivers" list of the struct returned by describe.
    def renew (self, urns, expiration_time, options=None):
        if options is None: options={}
        return "dummy Driver.renew needs to be redefined"

    # the answer to Delete on a given slice
    # returns: struct containing "geni_slivers" list of the struct returned by describe.
    def delete(self, urns, options=None):
        if options is None: options={}
        return "dummy Driver.delete needs to be redefined"

    # the answer to Shutdown on a given slice
    # returns: boolean
    def shutdown (self, xrn, options=None):
        if options is None: options={}
        return False
