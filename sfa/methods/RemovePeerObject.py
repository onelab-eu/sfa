from sfa.util.faults import UnknownSfaType, SfaInvalidArgument
from sfa.util.method import Method
from sfa.util.parameter import Parameter, Mixed
from sfa.util.table import SfaTable
from sfa.trust.credential import Credential

class RemovePeerObject(Method):
    """
    Remove an peer object from the PLC records of a local aggregate. 
    This method will be called by registry.remove() while removing 
    a record from the local aggreage's PLCDB and sfa table. This 
    method need not be directly called by end-user.
    
    @param cred credential string
    @param record record as stored in the local registry

    @return 1 if successful, faults otherwise 
    """

    interfaces = ['registry']
    
    accepts = [
        Parameter(str, "Credential string"),
        Parameter(dict, "Record dictionary"),
        Mixed(Parameter(str, "Human readable name of the original caller"),
              Parameter(None, "Origin hrn not specified"))
        ]

    returns = Parameter(int, "1 if successful")
    
    def call(self, cred, record, origin_hrn=None):
        user_cred = Credential(string=cred)

        #log the call
        if not origin_hrn:
            origin_hrn = user_cred.get_gid_caller().get_hrn()
        self.api.logger.info("interface: %s\tcaller-hrn: %s\ttarget-hrn: %s\tmethod-name: %s"%(self.api.interface, origin_hrn, record['hrn'], self.name))

        self.api.auth.check(cred, "remove")

        # Only allow the local interface or record owner to delete peer_records 
        try: self.api.auth.verify_object_permission(record['hrn'])
        except: self.api.auth.verify_cred_is_me(cred)
        
        table = SfaTable()
        hrn, type = record['hrn'], record['type']
        records = table.find({'hrn': hrn, 'type': type })
        for record in records:
            if record['peer_authority']:
                self.remove_plc_record(record)
                table.remove(record)
            
        return 1

    def remove_plc_record(self, record):
        type = record['type']        
        if type == "user":
            persons = self.api.plshell.GetPersons(self.api.plauth, {'person_id' : record['pointer']})
            if not persons:
                return 1
            person = persons[0]
            if person['peer_id']:
                peer = self.get_peer_name(person['peer_id']) 
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'person', person['person_id'], peer)
            self.api.plshell.DeletePerson(self.api.plauth, person['person_id'])
           
        elif type == "slice":
            slices=self.api.plshell.GetSlices(self.api.plauth, {'slice_id' : record['pointer']})
            if not slices:
                return 1
            slice=slices[0]
            if slice['peer_id']:
                peer = self.get_peer_name(slice['peer_id']) 
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'slice', slice['slice_id'], peer)
            self.api.plshell.DeleteSlice(self.api.plauth, slice['slice_id'])
        elif type == "authority":
            sites=self.api.plshell.GetSites(self.api.plauth, {'site_id' : record['pointer']})
            if not sites:
                return 1
            site=sites[0]
            if site['peer_id']:
                peer = self.get_peer_name(site['peer_id']) 
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'site', site['site_id'], peer)
            self.api.plshell.DeleteSite(self.api.plauth, site['site_id'])
           
        else:
            raise UnknownSfaType(type)

        return 1

    def get_peer_name(self, peer_id):
        peers = self.api.plshell.GetPeers(self.api.plauth, [peer_id], ['peername', 'shortname', 'hrn_root'])
        if not peers:
            raise SfaInvalidArgument, "No such peer"
        peer = peers[0]
        return peer['shortname'] 



