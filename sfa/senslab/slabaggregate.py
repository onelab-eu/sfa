import time
from sfa.util.xrn import hrn_to_urn, urn_to_hrn, get_authority

from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.versions.slabv1Node import SlabPosition
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.services import Services
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.version_manager import VersionManager


from sfa.rspecs.elements.versions.slabv1Node import SlabNode
from sfa.util.sfalogging import logger

from sfa.util.xrn import Xrn

def slab_xrn_to_hostname(xrn):
    return Xrn.unescape(Xrn(xrn=xrn, type='node').get_leaf())

def slab_xrn_object(root_auth, hostname):
    """Attributes are urn and hrn.
    Get the hostname using slab_xrn_to_hostname on the urn.
    
    """
    return Xrn('.'.join( [root_auth, Xrn.escape(hostname)]), type='node')

class SlabAggregate:

    sites = {}
    nodes = {}
    api = None
    interfaces = {}
    links = {}
    node_tags = {}
    
    prepared = False

    user_options = {}
    
    def __init__(self, driver):
        self.driver = driver

    def get_slice_and_slivers(self, slice_xrn, login=None):
        """
        Returns a dict of slivers keyed on the sliver's node_id
        """
        slivers = {}
        sfa_slice = None
        if not slice_xrn:
            return (sfa_slice, slivers)
        slice_urn = hrn_to_urn(slice_xrn, 'slice')
        slice_hrn, _ = urn_to_hrn(slice_xrn)
        slice_name = slice_hrn

        slices = self.driver.GetSlices(slice_filter= str(slice_name), \
                                                slice_filter_type = 'slice_hrn', login=login)
        
        logger.debug("Slabaggregate api \tget_slice_and_slivers \
                        sfa_slice %s \r\n slices %s self.driver.hrn %s" \
                        %(sfa_slice, slices, self.driver.hrn))
        if not slices:
            return (sfa_slice, slivers)
        #if isinstance(sfa_slice, list):
            #sfa_slice = slices[0]
        #else:
            #sfa_slice = slices

        # sort slivers by node id , if there is a job
        #and therfore, node allocated to this slice
        for sfa_slice in slices:
            try:
                node_ids_list =  sfa_slice['node_ids']  
            except KeyError:
                logger.log_exc("SLABAGGREGATE \t \
                                        get_slice_and_slivers KeyError ")
                continue
                                        
            for node in node_ids_list:
                sliver_xrn = Xrn(slice_urn, type='sliver', id=node)
                sliver_xrn.set_authority(self.driver.hrn)
                #node_id = self.driver.root_auth + '.' + node_id
                sliver = Sliver({'sliver_id':sliver_xrn.urn, 
                                'name': sfa_slice['hrn'],
                                'type': 'slab-node', 
                                'tags': []})
                
                slivers[node] = sliver
          
        
        #Add default sliver attribute :
        #connection information for senslab
        if get_authority (sfa_slice['hrn']) == self.driver.root_auth: 
            tmp = sfa_slice['hrn'].split('.')
            ldap_username = tmp[1].split('_')[0]
            vmaddr = 'ssh ' + ldap_username + '@grenoble.senslab.info'
            slivers['default_sliver'] =  {'vm': vmaddr , 'login': ldap_username}
            
        #TODO get_slice_and_slivers Find the login of the external user

        logger.debug("SLABAGGREGATE api get_slice_and_slivers  slivers %s "\
                                                             %(slivers))
        return (slices, slivers)
            

        
    def get_nodes(self, slices=None, slivers=[], options={}):
        # NT: the semantic of this function is not clear to me :
        # if slice is not defined, then all the nodes should be returned
        # if slice is defined, we should return only the nodes that 
        # are part of this slice
        # but what is the role of the slivers parameter ?
        # So i assume that slice['node_ids'] will be the same as slivers for us
        #filter_dict = {}
        #if slice_xrn:
            #if not slices or not slices['node_ids']:
                #return ([],[])
        #tags_filter = {}
        
        # get the granularity in second for the reservation system
        grain = self.driver.GetLeaseGranularity()
        
        # Commenting this part since all nodes should be returned, 
        # even if a slice is provided
        #if slice :
        #    if 'node_ids' in slice and slice['node_ids']:
        #        #first case, a non empty slice was provided
        #        filter['hostname'] = slice['node_ids']
        #        tags_filter=filter.copy()
        #        nodes = self.driver.GetNodes(filter['hostname'])
        #    else :
        #        #second case, a slice was provided, but is empty
        #        nodes={}
        #else :
        #    #third case, no slice was provided
        #    nodes = self.driver.GetNodes()
        nodes = self.driver.GetNodes()
        #geni_available = options.get('geni_available')    
        #if geni_available:
            #filter['boot_state'] = 'boot'     
       
        #filter.update({'peer_id': None})
        #nodes = self.driver.GetNodes(filter['hostname'])
        
        #site_ids = []
        #interface_ids = []
        #tag_ids = []
        nodes_dict = {}
        for node in nodes:
           
            nodes_dict[node['node_id']] = node
        #logger.debug("SLABAGGREGATE api get_nodes nodes  %s "\
                                                             #%(nodes ))
        # get sites
        #sites_dict  = self.get_sites({'site_id': site_ids}) 
        # get interfaces
        #interfaces = self.get_interfaces({'interface_id':interface_ids}) 
        # get tags
        #node_tags = self.get_node_tags(tags_filter)
        
        #if slices, this means we got to list all the nodes given to this slice
        # Make a list of all the nodes in the slice before getting their attributes
        rspec_nodes = []
        slice_nodes_list = []
        logger.debug("SLABAGGREGATE api get_nodes slice_nodes_list  %s "\
                                                             %(slices )) 
        if slices:
            for one_slice in slices:
                try:
                    slice_nodes_list = one_slice['node_ids']
                except KeyError:
                    pass
                #for node in one_slice['node_ids']:
                    #slice_nodes_list.append(node)
                   
        reserved_nodes = self.driver.GetNodesCurrentlyInUse()
        logger.debug("SLABAGGREGATE api get_nodes slice_nodes_list  %s "\
                                                             %(slice_nodes_list)) 
        for node in nodes:
            # skip whitelisted nodes
            #if node['slice_ids_whitelist']:
                #if not slice or slice['slice_id'] not in node['slice_ids_whitelist']:
                    #continue
            #rspec_node = Node()
            #logger.debug("SLABAGGREGATE api get_nodes node  %s "\
                                                             #%(node)) 
            if slice_nodes_list == [] or node['hostname'] in slice_nodes_list:
                   
                rspec_node = SlabNode()
                # xxx how to retrieve site['login_base']
                #site_id=node['site_id']
                #site=sites_dict[site_id]
                rspec_node['mobile'] = node['mobile']
                rspec_node['archi'] = node['archi']
                rspec_node['radio'] = node['radio']
    
                slab_xrn = slab_xrn_object(self.driver.root_auth, node['hostname'])
                rspec_node['component_id'] = slab_xrn.urn
                rspec_node['component_name'] = node['hostname']  
                rspec_node['component_manager_id'] = \
                                hrn_to_urn(self.driver.root_auth, 'authority+sa')
                
                # Senslab's nodes are federated : there is only one authority 
                # for all Senslab sites, registered in SFA.
                # Removing the part including the site 
                # in authority_id SA 27/07/12
                rspec_node['authority_id'] = rspec_node['component_manager_id']  
    
                # do not include boot state (<available> element)
                #in the manifest rspec
                
               
                rspec_node['boot_state'] = node['boot_state']
                if node['hostname'] in reserved_nodes:
                    rspec_node['boot_state'] = "Reserved"
                rspec_node['exclusive'] = 'true'
                rspec_node['hardware_types'] = [HardwareType({'name': 'slab-node'})]
    
                # only doing this because protogeni rspec needs
                # to advertise available initscripts 
                # add site/interface info to nodes.
                # assumes that sites, interfaces and tags have already been prepared.
                #site = sites_dict[node['site_id']]
                location = Location({'country':'France'})
                rspec_node['location'] = location
            
            
                position = SlabPosition()
                for field in position :
                    try:
                        position[field] = node[field]
                    except KeyError, error :
                        logger.log_exc("SLABAGGREGATE\t get_nodes \
                                                        position %s "%(error))
    
                rspec_node['position'] = position
                #rspec_node['interfaces'] = []
               
                # Granularity
                granularity = Granularity({'grain': grain})
                rspec_node['granularity'] = granularity
                rspec_node['tags'] = []
                if node['hostname'] in slivers:
                    # add sliver info
                    sliver = slivers[node['hostname']]
                    rspec_node['sliver_id'] = sliver['sliver_id']
                    rspec_node['client_id'] = node['hostname']
                    rspec_node['slivers'] = [sliver]
                    
                    # slivers always provide the ssh service
                    login = Login({'authentication': 'ssh-keys', 'hostname': node['hostname'], 'port':'22', 'username': sliver['name']})
                    service = Services({'login': login})
                    rspec_node['services'] = [service]
                rspec_nodes.append(rspec_node)

        return (rspec_nodes)       

    def get_leases(self, slice_record = None, options = {}):
    
        now = int(time.time())
        lease_filter = {'clip': now }

        #if slice_record:
            #lease_filter.update({'name': slice_record['name']})
        return_fields = ['lease_id', 'hostname', 'site_id', \
                            'name', 'start_time', 'duration']
        #leases = self.driver.GetLeases(lease_filter)
        leases = self.driver.GetLeases()
        grain = self.driver.GetLeaseGranularity()
        site_ids = []
        rspec_leases = []
        for lease in leases:
            #as many leases as there are nodes in the job 
            for node in lease['reserved_nodes']: 
                rspec_lease = Lease()
                rspec_lease['lease_id'] = lease['lease_id']
                #site = node['site_id']
                slab_xrn = slab_xrn_object(self.driver.root_auth, node)
                rspec_lease['component_id'] = slab_xrn.urn
                #rspec_lease['component_id'] = hostname_to_urn(self.driver.hrn, \
                                        #site, node['hostname'])
                try:
                    rspec_lease['slice_id'] = lease['slice_id']
                except KeyError:
                    #No info on the slice used in slab_xp table
                    pass
                rspec_lease['start_time'] = lease['t_from']
                rspec_lease['duration'] = (lease['t_until'] - lease['t_from']) \
                                                                    / grain   
                rspec_leases.append(rspec_lease)
        return rspec_leases    
        
   
        #rspec_leases = []
        #for lease in leases:
       
            #rspec_lease = Lease()
            
            ## xxx how to retrieve site['login_base']

            #rspec_lease['lease_id'] = lease['lease_id']
            #rspec_lease['component_id'] = hostname_to_urn(self.driver.hrn, \
                                        #site['login_base'], lease['hostname'])
            #slice_hrn = slicename_to_hrn(self.driver.hrn, lease['name'])
            #slice_urn = hrn_to_urn(slice_hrn, 'slice')
            #rspec_lease['slice_id'] = slice_urn
            #rspec_lease['t_from'] = lease['t_from']
            #rspec_lease['t_until'] = lease['t_until']          
            #rspec_leases.append(rspec_lease)
        #return rspec_leases   
#from plc/aggregate.py 
    def get_rspec(self, slice_xrn=None, login=None, version = None, options={}):

        rspec = None
        version_manager = VersionManager()	
        version = version_manager.get_version(version)
        logger.debug("SlabAggregate \t get_rspec ***version %s \
                    version.type %s  version.version %s options %s \r\n" \
                    %(version,version.type,version.version,options))

        if not slice_xrn:
            rspec_version = version_manager._get_version(version.type, \
                                                    version.version, 'ad')

        else:
            rspec_version = version_manager._get_version(version.type, \
                                                version.version, 'manifest')
           
        slices, slivers = self.get_slice_and_slivers(slice_xrn, login)
        #at this point sliver may be empty if no senslab job 
        #is running for this user/slice.
        rspec = RSpec(version=rspec_version, user_options=options)

        
        #if slice and 'expires' in slice:
           #rspec.xml.set('expires',  datetime_to_epoch(slice['expires']))
         # add sliver defaults
        #nodes, links = self.get_nodes(slice, slivers)
        logger.debug("\r\n \r\n SlabAggregate \tget_rspec ******* slice_xrn %s slices  %s\r\n \r\n"\
                                            %(slice_xrn, slices)) 
                                            
        try:                                    
            lease_option = options['list_leases']
        except KeyError:
            #If no options are specified, at least print the resources
            lease_option = 'all'
           #if slice_xrn :
               #lease_option = 'all'
            pass 
        
        if lease_option in ['all', 'resources']:
        #if not options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'leases':
            nodes = self.get_nodes(slices, slivers) 
            #In case creating a job,  slice_xrn is not set to None
            rspec.version.add_nodes(nodes)
            if slice_xrn :
                #Get user associated with this slice
                #user = dbsession.query(RegRecord).filter_by(record_id = \
                                                #slices['record_id_user']).first()

                #ldap_username = (user.hrn).split('.')[1]
                
                
                #for one_slice in slices :
                ldap_username = slices[0]['hrn']
                tmp = ldap_username.split('.')
                ldap_username = tmp[1].split('_')[0]
              
                if version.type == "Slab":
                    rspec.version.add_connection_information(ldap_username)

            default_sliver = slivers.get('default_sliver', [])
            if default_sliver:
                #default_sliver_attribs = default_sliver.get('tags', [])
                logger.debug("SlabAggregate \tget_rspec **** \
                        default_sliver%s \r\n" %(default_sliver))
                for attrib in default_sliver:
                    rspec.version.add_default_sliver_attribute(attrib, \
                                                               default_sliver[attrib])  
        if lease_option in ['all','leases']:                                                         
        #if options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'resources':
            leases = self.get_leases(slices)
            rspec.version.add_leases(leases)
            
        #logger.debug("SlabAggregate \tget_rspec ******* rspec_toxml %s \r\n"\
                                            #%(rspec.toxml())) 
        return rspec.toxml()          
