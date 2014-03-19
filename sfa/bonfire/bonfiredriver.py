import bonfire
from sfa.managers.driver import Driver

""" an attempt to do a sfawrap plugin document """

class Bonfiredriver(Driver):

    def __init__ (self, config):
        """ this is the hrn attached to the running server """
        self.config = config

    def augment_records_with_testbed_info (self, sfa_records):
        return sfa_records

    def register (self, sfa_record, hrn, pub_key) :
        return -1

    def remove (self, sfa_record):
        return True

    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        return True

    def update_relation (self, subject_type, target_type, relation_name, subject_id, link_ids):
        pass

    ########################################
    ########## aggregate oriented
    ########################################

    def __parameter__ (self, action):
        options={}
        if action == "allocate":
           options['user_name']    = input("Enter your name: ")
           options['groups']       = input("Enter your group: ")
           options['description']  = input("Enter a description: ")
           options['walltime']     = input("Enter a walltime: ")
           options['Vslice_name']  = input("Enter a slice name: ")
        elif action == "provision" or action == "delete":
           options['number']   = input("Enter a number (experiment): ")
           options['status']   = input("Enter a status (running delete): ")
        elif action == "create":
           options['groups']       = input("Enter your group: ")
           options['description']  = input("Enter a description: ")
           options['number']       = input("Enter a number (experiment): ")
           options['testbed']      = input("Enter a testbed (fr-inria or uk-epcc): ")

    def testbed_name (self): return "Bonfire"

    def aggregate_version (self): return {}

    def list_resources (self, version=None, options={}):
        rspec = bonfire.bonsources()
        hashres ={'geni_rspec': rspec, 'geni_urn':'None','geni_slivers':[{'geni_sliver_urn':'None','geni_expires':'None','geni_allocation_status':'None','geni_operational_status':'None'}]}
        return hashres

    def describe (self, urns, version, options={}):
        return "dummy Driver.describe needs to be redefined"

    def allocate (self, urn=None, rspec_string=None, expiration=None, options={}):
        """ options= {"user_name":"nlebreto","groups":"nlebreto","description":"exp","walltime":"125","slice_name":"topdomain.dummy.nicolas"} """
        if bool(options):
           sendallocate = bonfire.allocate(options['user_name'],options['groups'],options['description'],options['walltime'],options['slice_name'])
           return "allocate done"
        else:
           return "options not well defined for allocate"

    def provision(self, urns=None, options={}):
        if bool(options):
           bonfire.provisioning(options['number'],options['status'])
           return "provision done"
        else:
           return "dummy Driver.provision needs to be redefined"

    def perform_operational_action (self, urns=None, action=None, options={}):
        if bool(options):
           bonfire.create_vm(options['testbed'],options['number'],options['description'],options['groups'])
           return "create vm"
        else:
           return "dummy Driver.perform_operational_action needs to be redefined"

    def status (self, urns, options={}):
        return "dummy Driver.status needs to be redefined"

    def renew (self, urns, expiration_time, options={}):
        return "dummy Driver.renew needs to be redefined"

    def delete(self, urns, options={}):
        if bool(options):
           bonfire.provisioning(options['number'],options['status'])
           return "provision done"
        else:
           return "dummy Driver.delete needs to be redefined"

    def shutdown (self, xrn, options={}):
        return False
