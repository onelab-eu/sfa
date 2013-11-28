from sfa.rspecs.versions.pgv2 import PGv2

class GENIv3(PGv2):
    type = 'GENI'
    content_type = 'ad'
    version = '3'
    schema = 'http://www.geni.net/resources/rspec/3/ad.xsd'
    namespace = 'http://www.geni.net/resources/rspec/3'
    extensions = {
        'flack': "http://www.protogeni.net/resources/rspec/ext/flack/1",
        'planetlab': "http://www.planet-lab.org/resources/sfa/ext/planetlab/1",
        'plos': "http://www.planet-lab.org/resources/sfa/ext/plos/1",
    }
    namespaces = dict(extensions.items() + [('default', namespace)])
    elements = []


class GENIv3Ad(GENIv3):
    enabled = True
    content_type = 'ad'
    schema = 'http://www.geni.net/resources/rspec/3/ad.xsd'
    template = """<rspec type="advertisement" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.geni.net/resources/rspec/3" xmlns:plos="http://www.planet-lab.org/resources/sfa/ext/plos/1" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xmlns:opstate="http://www.geni.net/resources/rspec/ext/opstate/1" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/ad.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd http://www.planet-lab.org/resources/sfa/ext/plos/1 http://www.planet-lab.org/resources/sfa/ext/plos/1/plos.xsd http://www.geni.net/resources/rspec/ext/opstate/1 http://www.geni.net/resources/rspec/ext/opstate/1/ad.xsd">
    <opstate:rspec_opstate aggregate_manager_id="urn:publicid:IDN+plc+authority+cm" start="geni_notready">
      <opstate:sliver_type name="plab-vserver" />
      <opstate:sliver_type name="plos-pc" />
      <opstate:state name="geni_notready">
        <opstate:action name="geni_start" next="geni_ready">
          <opstate:description>Boot the node</opstate:description>
        </opstate:action>
        <opstate:description>VMs begin powered down or inactive. They
        must be explicitly booted before use.</opstate:description>
      </opstate:state>
      <opstate:state name="geni_ready">
        <opstate:description>The node is up and ready to use.</opstate:description>
      </opstate:state>
      <opstate:state name="geni_failed">
        <opstate:description>The node has failed and requires administrator
        intervention before it can be used. Please contact support
        for assistance.</opstate:description>
      </opstate:state>
    </opstate:rspec_opstate>
</rspec>"""

class GENIv3Request(GENIv3):
    enabled = True
    content_type = 'request'
    schema = 'http://www.geni.net/resources/rspec/3/request.xsd'
    template = '<rspec type="request" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.geni.net/resources/rspec/3" xmlns:plos="http://www.planet-lab.org/resources/sfa/ext/plos/1" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/request.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd http://www.planet-lab.org/resources/sfa/ext/plos/1 http://www.planet-lab.org/resources/sfa/ext/plos/1/plos.xsd"/>'

class GENIv2Manifest(GENIv3):
    enabled = True
    content_type = 'manifest'
    schema = 'http://www.geni.net/resources/rspec/3/manifest.xsd'
    template = '<rspec type="manifest" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.geni.net/resources/rspec/3" xmlns:plos="http://www.planet-lab.org/resources/sfa/ext/plos/1" xmlns:flack="http://www.protogeni.net/resources/rspec/ext/flack/1" xmlns:planetlab="http://www.planet-lab.org/resources/sfa/ext/planetlab/1" xmlns:ssh-user="http://www.geni.net/resources/rspec/ext/user/1" xsi:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/manifest.xsd http://www.planet-lab.org/resources/sfa/ext/planetlab/1 http://www.planet-lab.org/resources/sfa/ext/planetlab/1/planetlab.xsd http://www.planet-lab.org/resources/sfa/ext/plos/1 http://www.planet-lab.org/resources/sfa/ext/plos/1/plos.xsd http://www.geni.net/resources/rspec/ext/user/1 http://www.geni.net/resources/rspec/ext/user/1/manifest.xsd"/>'
