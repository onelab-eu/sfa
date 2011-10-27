from sfa.plc.aggregate import Aggregate
from sfa.managers.vini.topology import PhysicalLinks
from sfa.rspecs.elements.link import Link
from sfa.util.xrn import hrn_to_urn
from sfa.util.plxrn import PlXrn

class ViniAggregate(Aggregate):

    def prepare_links(self, force=False):
        for (site_id1, site_id2) in PhysicalLinks:
            link = Link()
            if not site_id1 in self.sites or site_id2 not in self.sites:
                continue 
            site1 = self.sites[site_id1]
            site2 = self.sites[site_id2]
            # get hrns
            site1_hrn = self.api.hrn + '.' + site1['login_base']
            site2_hrn = self.api.hrn + '.' + site2['login_base']
            # get the first node
            node1 = self.nodes[site1['node_id'][0]]
            node2 = self.nodes[site2['node_id'][0]]
        
            # set interfaces
            # just get first interface of the first node 
            if1_xrn = PlXrn(auth=self.api.hrn, interface='node%s:eth0' % (node1['node_id']))   
            if2_xrn = PlXrn(auth=self.api.hrn, interface='node%s:eth0' % (node2['node_id']))
               
            if1 = Interface({'component_id': if1_xrn.urn} )  
            if2 = Interface({'component_id': if2_xrn.urn} )  
            
            # set link
            link = Link({'capacity': '1000000', 'latency': '0', 'packet_loss': '0', 'type': 'ipv4'})
            link['interface1'] = if1
            link['interface2'] = if2
            link['component_name'] = "%s:%s" % (site1['login_base'], site2['login_base'])
            link['component_id'] = PlXrn(auth=self.api.hrn, link=link['component_name'])
            link['component_manager_id'] =  hrn_to_urn(self.api.hrn, 'authority+am')
            self.links[link['component_name']] = link
        
        
