#
# an adapter on top of driver implementing AM API v2 to be AM API v3 compliant
#
import sys
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, urn_to_hrn, hrn_to_urn, get_leaf, get_authority
from sfa.util.cache import Cache
from sfa.rspecs.rspec import RSpec
from sfa.storage.model import SliverAllocation

class V2ToV3Adapter:

    def __init__ (self, api):
        config = api.config
        flavour = config.SFA_GENERIC_FLAVOUR
        # to be cleaned
        if flavour == "nitos":
            from sfa.nitos.nitosdriver import NitosDriver
            self.driver = NitosDriver(api)
        elif flavour == "fd":
            from sfa.federica.fddriver import FdDriver
            self.driver = FdDriver(api)
        else:
          logger.error("V2ToV3Adapter: Unknown Flavour !!!\n Supported Flavours: nitos, fd")
         
        # Caching 
        if config.SFA_AGGREGATE_CACHING:
            if self.driver.cache:
                self.cache = self.driver.cache
            else:
                self.cache = Cache()


    def __getattr__(self, name):
        def func(*args, **kwds):
            if name == "list_resources":
                (version, options) = args
                slice_urn = slice_hrn = None
                creds = []
                rspec = getattr(self.driver, "list_resources")(slice_urn, slice_hrn, [], options) 
                result = rspec

            elif name == "describe":
                (urns, version, options) = args
                slice_urn = urns[0]
                slice_hrn, type = urn_to_hrn(slice_urn)
                creds = []
                rspec = getattr(self.driver, "list_resources")(slice_urn, slice_hrn, creds, options)
    
                # SliverAllocation
                if len(urns) == 1 and Xrn(xrn=urns[0]).type == 'slice':
                    constraint = SliverAllocation.slice_urn.in_(urns)
                else:
                    constraint = SliverAllocation.sliver_id.in_(urns)
 
                sliver_allocations = self.driver.api.dbsession().query (SliverAllocation).filter        (constraint)
                sliver_status = getattr(self.driver, "sliver_status")(slice_urn, slice_hrn)               
                if 'geni_expires' in sliver_status.keys():
                    geni_expires = sliver_status['geni_expires']
                else: 
                    geni_expires = ''
                
                geni_slivers = []
                for sliver_allocation in sliver_allocations:
                    geni_sliver = {}
                    geni_sliver['geni_expires'] = geni_expires
                    geni_sliver['geni_allocation'] = sliver_allocation.allocation_state
                    geni_sliver['geni_sliver_urn'] = sliver_allocation.sliver_id
                    geni_sliver['geni_error'] = ''
                    if geni_sliver['geni_allocation'] == 'geni_allocated':
                        geni_sliver['geni_operational_status'] = 'geni_pending_allocation'
                    else: 
                        geni_sliver['geni_operational_status'] = 'geni_ready'
                    geni_slivers.append(geni_sliver)


                result = {'geni_urn': slice_urn,
                'geni_rspec': rspec,
                'geni_slivers': geni_slivers}

            elif name == "allocate":
                (slice_urn, rspec_string, expiration, options) = args
                slice_hrn, type = urn_to_hrn(slice_urn)
                creds = []
                users = options.get('sfa_users', [])
                manifest_string = getattr(self.driver, "create_sliver")(slice_urn, slice_hrn, creds, rspec_string, users, options)
                
                # slivers allocation
                rspec = RSpec(manifest_string)
                slivers = rspec.version.get_nodes_with_slivers()
                
                ##SliverAllocation
                for sliver in slivers:
                     client_id = sliver['client_id']
                     component_id = sliver['component_id']
                     component_name = sliver['component_name']
                     slice_name = slice_hrn.replace('.','-')
                     component_short_name = component_name.split('.')[0]
                     # self.driver.hrn
                     sliver_hrn = '%s.%s-%s' % (self.driver.hrn, slice_name, component_short_name)
                     sliver_id = Xrn(sliver_hrn, type='sliver').urn
                     record = SliverAllocation(sliver_id=sliver_id, 
                                      client_id=client_id,
                                      component_id=component_id,
                                      slice_urn = slice_urn,
                                      allocation_state='geni_allocated')    
     
                     record.sync(self.driver.api.dbsession())

               
                # return manifest
                rspec_version = RSpec(rspec_string).version
                rspec_version_str = "%s"%rspec_version
                options['geni_rspec_version'] = {'version': rspec_version_str.split(' ')[1], 'type': rspec_version_str.lower().split(' ')[0]}
                result = self.describe([slice_urn], rspec_version, options)
                
            elif name == "provision": 
                (urns, options) = args
                if len(urns) == 1 and Xrn(xrn=urns[0]).type == 'slice':
                   constraint = SliverAllocation.slice_urn.in_(urns)
                else:
                   constraint = SliverAllocation.sliver_id.in_(urns)
                
                dbsession = self.driver.api.dbsession()
                sliver_allocations = dbsession.query (SliverAllocation).filter(constraint)
                for sliver_allocation in sliver_allocations:
                     sliver_allocation.allocation_state = 'geni_provisioned'
                
                dbsession.commit()
                result = self.describe(urns, '', options)

            elif name == "status":
                urns = args
                options = {}
                options['geni_rspec_version'] = {'version': '3', 'type': 'GENI'}
                descr = self.describe(urns[0], '', options)
                result = {'geni_urn': descr['geni_urn'],
                          'geni_slivers': descr['geni_slivers']}

            elif name == "delete":
                (urns, options) = args
                slice_urn = urns[0]
                slice_hrn, type = urn_to_hrn(slice_urn)
                creds = []
                options['geni_rspec_version'] = {'version': '3', 'type': 'GENI'}
                descr = self.describe(urns, '', options)
                result = []
                for sliver_allocation in descr['geni_slivers']:
                     geni_sliver = {'geni_sliver_urn': sliver_allocation['geni_sliver_urn'],
                                    'geni_allocation_status': 'geni_unallocated',
                                    'geni_expires': sliver_allocation['geni_expires'],
                                    'geni_error': sliver_allocation['geni_error']}
                       
                     result.append(geni_sliver)
                     
                getattr(self.driver, "delete_sliver")(slice_urn, slice_hrn, creds, options) 
             
                #SliverAllocation
                constraints = SliverAllocation.slice_urn.in_(urns)
                dbsession = self.driver.api.dbsession()
                sliver_allocations = dbsession.query(SliverAllocation).filter(constraints)
                sliver_ids = [sliver_allocation.sliver_id for sliver_allocation in sliver_allocations]
                SliverAllocation.delete_allocations(sliver_ids, dbsession)
                

            elif name == "renew":
                (urns, expiration_time, options) = args
                slice_urn = urns[0]    
                slice_hrn, type = urn_to_hrn(slice_urn)
                creds = []

                getattr(self.driver, "renew_sliver")(slice_urn, slice_hrn, creds, expiration_time, options)

                options['geni_rspec_version'] = {'version': '3', 'type': 'GENI'}
                descr = self.describe(urns, '', options)
                result = descr['geni_slivers']
                

            elif name == "perform_operational_action":
                (urns, action, options) = args
                options['geni_rspec_version'] = {'version': '3', 'type': 'GENI'}
                result = self.describe(urns, '', options)['geni_slivers']


            else: 
                # same as v2 ( registry methods) 
                result=getattr(self.driver, name)(*args, **kwds)
            return result
        return func
