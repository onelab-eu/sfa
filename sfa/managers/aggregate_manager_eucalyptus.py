from __future__ import with_statement 

import sys
import os, errno
import logging
import datetime
from multiprocessing import Process
from time import sleep

import boto
from boto.ec2.regioninfo import RegionInfo
from boto.exception import EC2ResponseError
from ConfigParser import ConfigParser
from xmlbuilder import XMLBuilder
from lxml import etree as ET
from sqlobject import *

from sfa.util.faults import InvalidRSpec 
from sfa.util.xrn import urn_to_hrn, Xrn
from sfa.util.plxrn import hrn_to_pl_slicename, slicename_to_hrn
from sfa.util.callids import Callids
#comes with its own logging
#from sfa.util.sfalogging import logger
from sfa.util.version import version_core
from sfa.trust.credential import Credential
from sfa.plc.plaggregate import PlAggregate
# No Slice symbol in there
#from sfa.plc.plslices import Slice, Slices
from sfa.plc.plslices import PlSlices
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec
# not sure what this used to be nor where it is now defined
#from sfa.rspecs.sfa_rspec import sfa_rspec_version
# most likely this should now be
#from sfa.rspecs.version_manager import VersionManager

##
# Meta data of an instance.
#
class Meta(SQLObject):
    instance   = SingleJoin('EucaInstance')
    state      = StringCol(default = 'new')
    pub_addr   = StringCol(default = None)
    pri_addr   = StringCol(default = None)
    start_time = DateTimeCol(default = None)

##
# A representation of an Eucalyptus instance. This is a support class
# for instance <-> slice mapping.
#
class EucaInstance(SQLObject):
    instance_id = StringCol(unique=True, default=None)
    kernel_id   = StringCol()
    image_id    = StringCol()
    ramdisk_id  = StringCol()
    inst_type   = StringCol()
    key_pair    = StringCol()
    slice       = ForeignKey('Slice')
    meta        = ForeignKey('Meta')

    ##
    # Contacts Eucalyptus and tries to reserve this instance.
    # 
    # @param botoConn A connection to Eucalyptus.
    # @param pubKeys A list of public keys for the instance.
    #
    def reserveInstance(self, botoConn, pubKeys):
        logger = logging.getLogger('EucaAggregate')
        logger.info('Reserving an instance: image: %s, kernel: ' \
                    '%s, ramdisk: %s, type: %s, key: %s' % \
                    (self.image_id, self.kernel_id, self.ramdisk_id,
                    self.inst_type, self.key_pair))

        try:
            reservation = botoConn.run_instances(self.image_id,
                                                 kernel_id = self.kernel_id,
                                                 ramdisk_id = self.ramdisk_id,
                                                 instance_type = self.inst_type,
                                                 key_name  = self.key_pair,
                                                 user_data = pubKeys)
            for instance in reservation.instances:
                self.instance_id = instance.id

        # If there is an error, destroy itself.
        except EC2ResponseError, ec2RespErr:
            errTree = ET.fromstring(ec2RespErr.body)
            msg = errTree.find('.//Message')
            logger.error(msg.text)
            self.destroySelf()

##
# A representation of a PlanetLab slice. This is a support class
# for instance <-> slice mapping.
#
class Slice(SQLObject):
    slice_hrn = StringCol()
    #slice_index = DatabaseIndex('slice_hrn')
    instances = MultipleJoin('EucaInstance')

##
# A class that builds the RSpec for Eucalyptus.
#
class EucaRSpecBuilder(object):
    ##
    # Initizes a RSpec builder
    #
    # @param cloud A dictionary containing data about a 
    #              cloud (ex. clusters, ip)
    def __init__(self, cloud):
        self.eucaRSpec = XMLBuilder(format = True, tab_step = "  ")
        self.cloudInfo = cloud

    ##
    # Creates a request stanza.
    # 
    # @param num The number of instances to create.
    # @param image The disk image id.
    # @param kernel The kernel image id.
    # @param keypair Key pair to embed.
    # @param ramdisk Ramdisk id (optional).
    #
    def __requestXML(self, num, image, kernel, keypair, ramdisk = ''):
        xml = self.eucaRSpec
        with xml.request:
            with xml.instances:
                xml << str(num)
            with xml.kernel_image(id=kernel):
                xml << ''
            if ramdisk == '':
                with xml.ramdisk:
                    xml << ''
            else:
                with xml.ramdisk(id=ramdisk):
                    xml << ''
            with xml.disk_image(id=image):
                xml << ''
            with xml.keypair:
                xml << keypair

    ##
    # Creates the cluster stanza.
    #
    # @param clusters Clusters information.
    #
    def __clustersXML(self, clusters):
        cloud = self.cloudInfo
        xml = self.eucaRSpec

        for cluster in clusters:
            instances = cluster['instances']
            with xml.cluster(id=cluster['name']):
                with xml.ipv4:
                    xml << cluster['ip']
                with xml.vm_types:
                    for inst in instances:
                        with xml.vm_type(name=inst[0]):
                            with xml.free_slots:
                                xml << str(inst[1])
                            with xml.max_instances:
                                xml << str(inst[2])
                            with xml.cores:
                                xml << str(inst[3])
                            with xml.memory(unit='MB'):
                                xml << str(inst[4])
                            with xml.disk_space(unit='GB'):
                                xml << str(inst[5])
                            if 'instances' in cloud and inst[0] in cloud['instances']:
                                existingEucaInstances = cloud['instances'][inst[0]]
                                with xml.euca_instances:
                                    for eucaInst in existingEucaInstances:
                                        with xml.euca_instance(id=eucaInst['id']):
                                            with xml.state:
                                                xml << eucaInst['state']
                                            with xml.public_dns:
                                                xml << eucaInst['public_dns']

    def __imageBundleXML(self, bundles):
        xml = self.eucaRSpec
        with xml.bundles:
            for bundle in bundles.keys():
                with xml.bundle(id=bundle):
                    xml << ''

    ##
    # Creates the Images stanza.
    #
    # @param images A list of images in Eucalyptus.
    #
    def __imagesXML(self, images):
        xml = self.eucaRSpec
        with xml.images:
            for image in images:
                with xml.image(id=image.id):
                    with xml.type:
                        xml << image.type
                    with xml.arch:
                        xml << image.architecture
                    with xml.state:
                        xml << image.state
                    with xml.location:
                        xml << image.location

    ##
    # Creates the KeyPairs stanza.
    #
    # @param keypairs A list of key pairs in Eucalyptus.
    #
    def __keyPairsXML(self, keypairs):
        xml = self.eucaRSpec
        with xml.keypairs:
            for key in keypairs:
                with xml.keypair:
                    xml << key.name

    ##
    # Generates the RSpec.
    #
    def toXML(self):
        logger = logging.getLogger('EucaAggregate')
        if not self.cloudInfo:
            logger.error('No cloud information')
            return ''

        xml = self.eucaRSpec
        cloud = self.cloudInfo
        with xml.RSpec(type='eucalyptus'):
            with xml.network(name=cloud['name']):
                with xml.ipv4:
                    xml << cloud['ip']
                #self.__keyPairsXML(cloud['keypairs'])
                #self.__imagesXML(cloud['images'])
                self.__imageBundleXML(cloud['imageBundles'])
                self.__clustersXML(cloud['clusters'])
        return str(xml)

##
# A parser to parse the output of availability-zones.
#
# Note: Only one cluster is supported. If more than one, this will
#       not work.
#
class ZoneResultParser(object):
    def __init__(self, zones):
        self.zones = zones

    def parse(self):
        if len(self.zones) < 3:
            return
        clusterList = []
        cluster = {} 
        instList = []

        cluster['name'] = self.zones[0].name
        cluster['ip']   = self.zones[0].state

        for i in range(2, len(self.zones)):
            currZone = self.zones[i]
            instType = currZone.name.split()[1]

            stateString = currZone.state.split('/')
            rscString   = stateString[1].split()

            instFree      = int(stateString[0])
            instMax       = int(rscString[0])
            instNumCpu    = int(rscString[1])
            instRam       = int(rscString[2])
            instDiskSpace = int(rscString[3])

            instTuple = (instType, instFree, instMax, instNumCpu, instRam, instDiskSpace)
            instList.append(instTuple)
        cluster['instances'] = instList
        clusterList.append(cluster)

        return clusterList

class AggregateManagerEucalyptus:

    # The data structure used to represent a cloud.
    # It contains the cloud name, its ip address, image information,
    # key pairs, and clusters information.
    cloud = {}
    
    # The location of the RelaxNG schema.
    EUCALYPTUS_RSPEC_SCHEMA='/etc/sfa/eucalyptus.rng'
    
    _inited=False

    # the init_server mechanism has vanished
    def __init__ (self):
        if AggregateManagerEucalyptus._inited: return
        AggregateManagerEucalyptus.init_server()

    # Initialize the aggregate manager by reading a configuration file.
    @staticmethod
    def init_server():
        logger = logging.getLogger('EucaAggregate')
        fileHandler = logging.FileHandler('/var/log/euca.log')
        fileHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fileHandler)
        fileHandler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

        configParser = ConfigParser()
        configParser.read(['/etc/sfa/eucalyptus_aggregate.conf', 'eucalyptus_aggregate.conf'])
        if len(configParser.sections()) < 1:
            logger.error('No cloud defined in the config file')
            raise Exception('Cannot find cloud definition in configuration file.')
    
        # Only read the first section.
        cloudSec = configParser.sections()[0]
        AggregateManagerEucalyptus.cloud['name'] = cloudSec
        AggregateManagerEucalyptus.cloud['access_key'] = configParser.get(cloudSec, 'access_key')
        AggregateManagerEucalyptus.cloud['secret_key'] = configParser.get(cloudSec, 'secret_key')
        AggregateManagerEucalyptus.cloud['cloud_url']  = configParser.get(cloudSec, 'cloud_url')
        cloudURL = AggregateManagerEucalyptus.cloud['cloud_url']
        if cloudURL.find('https://') >= 0:
            cloudURL = cloudURL.replace('https://', '')
        elif cloudURL.find('http://') >= 0:
            cloudURL = cloudURL.replace('http://', '')
        (AggregateManagerEucalyptus.cloud['ip'], parts) = cloudURL.split(':')
    
        # Create image bundles
        images = self.getEucaConnection().get_all_images()
        AggregateManagerEucalyptus.cloud['images'] = images
        AggregateManagerEucalyptus.cloud['imageBundles'] = {}
        for i in images:
            if i.type != 'machine' or i.kernel_id is None: continue
            name = os.path.dirname(i.location)
            detail = {'imageID' : i.id, 'kernelID' : i.kernel_id, 'ramdiskID' : i.ramdisk_id}
            AggregateManagerEucalyptus.cloud['imageBundles'][name] = detail
    
        # Initialize sqlite3 database and tables.
        dbPath = '/etc/sfa/db'
        dbName = 'euca_aggregate.db'
    
        if not os.path.isdir(dbPath):
            logger.info('%s not found. Creating directory ...' % dbPath)
            os.mkdir(dbPath)
    
        conn = connectionForURI('sqlite://%s/%s' % (dbPath, dbName))
        sqlhub.processConnection = conn
        Slice.createTable(ifNotExists=True)
        EucaInstance.createTable(ifNotExists=True)
        Meta.createTable(ifNotExists=True)
    
        # Start the update process to keep track of the meta data
        # about Eucalyptus instance.
        Process(target=AggregateManagerEucalyptus.updateMeta).start()
    
        # Make sure the schema exists.
        if not os.path.exists(AggregateManagerEucalyptus.EUCALYPTUS_RSPEC_SCHEMA):
            err = 'Cannot location schema at %s' % AggregateManagerEucalyptus.EUCALYPTUS_RSPEC_SCHEMA
            logger.error(err)
            raise Exception(err)
    
    #
    # A separate process that will update the meta data.
    #
    @staticmethod    
    def updateMeta():
        logger = logging.getLogger('EucaMeta')
        fileHandler = logging.FileHandler('/var/log/euca_meta.log')
        fileHandler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(fileHandler)
        fileHandler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
        while True:
            sleep(30)
    
            # Get IDs of the instances that don't have IPs yet.
            dbResults = Meta.select(
                          AND(Meta.q.pri_addr == None,
                              Meta.q.state    != 'deleted')
                        )
            dbResults = list(dbResults)
            logger.debug('[update process] dbResults: %s' % dbResults)
            instids = []
            for r in dbResults:
                if not r.instance:
                    continue
                instids.append(r.instance.instance_id)
            logger.debug('[update process] Instance Id: %s' % ', '.join(instids))
    
            # Get instance information from Eucalyptus
            conn = self.getEucaConnection()
            vmInstances = []
            reservations = conn.get_all_instances(instids)
            for reservation in reservations:
                vmInstances += reservation.instances
    
            # Check the IPs
            instIPs = [ {'id':i.id, 'pri_addr':i.private_dns_name, 'pub_addr':i.public_dns_name}
                        for i in vmInstances if i.private_dns_name != '0.0.0.0' ]
            logger.debug('[update process] IP dict: %s' % str(instIPs))
    
            # Update the local DB
            for ipData in instIPs:
                dbInst = EucaInstance.select(EucaInstance.q.instance_id == ipData['id']).getOne(None)
                if not dbInst:
                    logger.info('[update process] Could not find %s in DB' % ipData['id'])
                    continue
                dbInst.meta.pri_addr = ipData['pri_addr']
                dbInst.meta.pub_addr = ipData['pub_addr']
                dbInst.meta.state    = 'running'
    
            self.dumpinstanceInfo()
    
    ##
    # Creates a connection to Eucalytpus. This function is inspired by 
    # the make_connection() in Euca2ools.
    #
    # @return A connection object or None
    #
    def getEucaConnection():
        accessKey = AggregateManagerEucalyptus.cloud['access_key']
        secretKey = AggregateManagerEucalyptus.cloud['secret_key']
        eucaURL   = AggregateManagerEucalyptus.cloud['cloud_url']
        useSSL    = False
        srvPath   = '/'
        eucaPort  = 8773
        logger    = logging.getLogger('EucaAggregate')
    
        if not accessKey or not secretKey or not eucaURL:
            logger.error('Please set ALL of the required environment ' \
                         'variables by sourcing the eucarc file.')
            return None
        
        # Split the url into parts
        if eucaURL.find('https://') >= 0:
            useSSL  = True
            eucaURL = eucaURL.replace('https://', '')
        elif eucaURL.find('http://') >= 0:
            useSSL  = False
            eucaURL = eucaURL.replace('http://', '')
        (eucaHost, parts) = eucaURL.split(':')
        if len(parts) > 1:
            parts = parts.split('/')
            eucaPort = int(parts[0])
            parts = parts[1:]
            srvPath = '/'.join(parts)
    
        return boto.connect_ec2(aws_access_key_id=accessKey,
                                aws_secret_access_key=secretKey,
                                is_secure=useSSL,
                                region=RegionInfo(None, 'eucalyptus', eucaHost), 
                                port=eucaPort,
                                path=srvPath)
    
    def ListResources(api, creds, options):
        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return ""
        # get slice's hrn from options
        xrn = options.get('geni_slice_urn', '')
        hrn, type = urn_to_hrn(xrn)
        logger = logging.getLogger('EucaAggregate')
    
        # get hrn of the original caller
        origin_hrn = options.get('origin_hrn', None)
        if not origin_hrn:
            origin_hrn = Credential(string=creds[0]).get_gid_caller().get_hrn()
    
        conn = self.getEucaConnection()
    
        if not conn:
            logger.error('Cannot create a connection to Eucalyptus')
            return 'Cannot create a connection to Eucalyptus'
    
        try:
            # Zones
            zones = conn.get_all_zones(['verbose'])
            p = ZoneResultParser(zones)
            clusters = p.parse()
            AggregateManagerEucalyptus.cloud['clusters'] = clusters
            
            # Images
            images = conn.get_all_images()
            AggregateManagerEucalyptus.cloud['images'] = images
            AggregateManagerEucalyptus.cloud['imageBundles'] = {}
            for i in images:
                if i.type != 'machine' or i.kernel_id is None: continue
                name = os.path.dirname(i.location)
                detail = {'imageID' : i.id, 'kernelID' : i.kernel_id, 'ramdiskID' : i.ramdisk_id}
                AggregateManagerEucalyptus.cloud['imageBundles'][name] = detail
    
            # Key Pairs
            keyPairs = conn.get_all_key_pairs()
            AggregateManagerEucalyptus.cloud['keypairs'] = keyPairs
    
            if hrn:
                instanceId = []
                instances  = []
    
                # Get the instances that belong to the given slice from sqlite3
                # XXX use getOne() in production because the slice's hrn is supposed
                # to be unique. For testing, uniqueness is turned off in the db.
                # If the slice isn't found in the database, create a record for the 
                # slice.
                matchedSlices = list(Slice.select(Slice.q.slice_hrn == hrn))
                if matchedSlices:
                    theSlice = matchedSlices[-1]
                else:
                    theSlice = Slice(slice_hrn = hrn)
                for instance in theSlice.instances:
                    instanceId.append(instance.instance_id)
    
                # Get the information about those instances using their ids.
                if len(instanceId) > 0:
                    reservations = conn.get_all_instances(instanceId)
                else:
                    reservations = []
                for reservation in reservations:
                    for instance in reservation.instances:
                        instances.append(instance)
    
                # Construct a dictionary for the EucaRSpecBuilder
                instancesDict = {}
                for instance in instances:
                    instList = instancesDict.setdefault(instance.instance_type, [])
                    instInfoDict = {} 
    
                    instInfoDict['id'] = instance.id
                    instInfoDict['public_dns'] = instance.public_dns_name
                    instInfoDict['state'] = instance.state
                    instInfoDict['key'] = instance.key_name
    
                    instList.append(instInfoDict)
                AggregateManagerEucalyptus.cloud['instances'] = instancesDict
    
        except EC2ResponseError, ec2RespErr:
            errTree = ET.fromstring(ec2RespErr.body)
            errMsgE = errTree.find('.//Message')
            logger.error(errMsgE.text)
    
        rspec = EucaRSpecBuilder(AggregateManagerEucalyptus.cloud).toXML()
    
        # Remove the instances records so next time they won't 
        # show up.
        if 'instances' in AggregateManagerEucalyptus.cloud:
            del AggregateManagerEucalyptus.cloud['instances']
    
        return rspec
    
    """
    Hook called via 'sfi.py create'
    """
    def CreateSliver(api, slice_xrn, creds, xml, users, options):
        call_id = options.get('call_id') 
        if Callids().already_handled(call_id): return ""
    
        logger = logging.getLogger('EucaAggregate')
        logger.debug("In CreateSliver")
    
        aggregate = PlAggregate(self.driver)
        slices = PlSlices(self.driver)
        (hrn, type) = urn_to_hrn(slice_xrn)
        peer = slices.get_peer(hrn)
        sfa_peer = slices.get_sfa_peer(hrn)
        slice_record=None
        if users:
            slice_record = users[0].get('slice_record', {})
    
        conn = self.getEucaConnection()
        if not conn:
            logger.error('Cannot create a connection to Eucalyptus')
            return ""
    
        # Validate RSpec
        schemaXML = ET.parse(AggregateManagerEucalyptus.EUCALYPTUS_RSPEC_SCHEMA)
        rspecValidator = ET.RelaxNG(schemaXML)
        rspecXML = ET.XML(xml)
        for network in rspecXML.iterfind("./network"):
            if network.get('name') != AggregateManagerEucalyptus.cloud['name']:
                # Throw away everything except my own RSpec
                # sfa_logger().error("CreateSliver: deleting %s from rspec"%network.get('id'))
                network.getparent().remove(network)
        if not rspecValidator(rspecXML):
            error = rspecValidator.error_log.last_error
            message = '%s (line %s)' % (error.message, error.line) 
            raise InvalidRSpec(message)
    
        """
        Create the sliver[s] (slice) at this aggregate.
        Verify HRN and initialize the slice record in PLC if necessary.
        """
    
        # ensure site record exists
        site = slices.verify_site(hrn, slice_record, peer, sfa_peer)
        # ensure slice record exists
        slice = slices.verify_slice(hrn, slice_record, peer, sfa_peer)
        # ensure person records exists
        persons = slices.verify_persons(hrn, slice, users, peer, sfa_peer)
    
        # Get the slice from db or create one.
        s = Slice.select(Slice.q.slice_hrn == hrn).getOne(None)
        if s is None:
            s = Slice(slice_hrn = hrn)
    
        # Process any changes in existing instance allocation
        pendingRmInst = []
        for sliceInst in s.instances:
            pendingRmInst.append(sliceInst.instance_id)
        existingInstGroup = rspecXML.findall(".//euca_instances")
        for instGroup in existingInstGroup:
            for existingInst in instGroup:
                if existingInst.get('id') in pendingRmInst:
                    pendingRmInst.remove(existingInst.get('id'))
        for inst in pendingRmInst:
            dbInst = EucaInstance.select(EucaInstance.q.instance_id == inst).getOne(None)
            if dbInst.meta.state != 'deleted':
                logger.debug('Instance %s will be terminated' % inst)
                # Terminate instances one at a time for robustness
                conn.terminate_instances([inst])
                # Only change the state but do not remove the entry from the DB.
                dbInst.meta.state = 'deleted'
                #dbInst.destroySelf()
    
        # Process new instance requests
        requests = rspecXML.findall(".//request")
        if requests:
            # Get all the public keys associate with slice.
            keys = []
            for user in users:
                keys += user['keys']
                logger.debug("Keys: %s" % user['keys'])
            pubKeys = '\n'.join(keys)
            logger.debug('Passing the following keys to the instance:\n%s' % pubKeys)
        for req in requests:
            vmTypeElement = req.getparent()
            instType = vmTypeElement.get('name')
            numInst  = int(req.find('instances').text)
            
            bundleName = req.find('bundle').text
            if not AggregateManagerEucalyptus.cloud['imageBundles'][bundleName]:
                logger.error('Cannot find bundle %s' % bundleName)
            bundleInfo = AggregateManagerEucalyptus.cloud['imageBundles'][bundleName]
            instKernel  = bundleInfo['kernelID']
            instDiskImg = bundleInfo['imageID']
            instRamDisk = bundleInfo['ramdiskID']
            instKey     = None
    
            # Create the instances
            for i in range(0, numInst):
                eucaInst = EucaInstance(slice      = s,
                                        kernel_id  = instKernel,
                                        image_id   = instDiskImg,
                                        ramdisk_id = instRamDisk,
                                        key_pair   = instKey,
                                        inst_type  = instType,
                                        meta       = Meta(start_time=datetime.datetime.now()))
                eucaInst.reserveInstance(conn, pubKeys)
    
        # xxx - should return altered rspec 
        # with enough data for the client to understand what's happened
        return xml
    
    ##
    # Return information on the IP addresses bound to each slice's instances
    #
    def dumpInstanceInfo():
        logger = logging.getLogger('EucaMeta')
        outdir = "/var/www/html/euca/"
        outfile = outdir + "instances.txt"
    
        try:
            os.makedirs(outdir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise
    
        dbResults = Meta.select(
            AND(Meta.q.pri_addr != None,
                Meta.q.state    == 'running')
            )
        dbResults = list(dbResults)
        f = open(outfile, "w")
        for r in dbResults:
            instId = r.instance.instance_id
            ipaddr = r.pri_addr
            hrn = r.instance.slice.slice_hrn
            logger.debug('[dumpInstanceInfo] %s %s %s' % (instId, ipaddr, hrn))
            f.write("%s %s %s\n" % (instId, ipaddr, hrn))
        f.close()
    
    def GetVersion(api):

        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        xrn=Xrn(api.hrn)
        version_more = {'interface':'aggregate',
                        'sfa': 1,
                        'geni_api': api.config.SFA_AGGREGATE_API_VERSION,
                        'testbed':'myplc',
                        'hrn':xrn.get_hrn(),
                        'geni_request_rspec_versions': request_rspec_versions,
                        'geni_ad_rspec_versions': ad_rspec_versions,
                        }
        return version_core(version_more)
