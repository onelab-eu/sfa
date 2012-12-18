from sfa.rspecs.versions.pgv2 import PGv2

class FedericaAd (PGv2):
    enabled = True
    type = 'Fedrica'
    content_type = 'ad'
    schema = 'http://sorch.netmode.ntua.gr/ws/RSpec/ad.xsd'
    namespace = 'http://sorch.netmode.ntua.gr/ws/RSpec'

class FedericaRequest (PGv2):
    enabled = True
    type = 'Fedrica'
    content_type = 'request'
    schema = 'http://sorch.netmode.ntua.gr/ws/RSpec/request.xsd'
    namespace = 'http://sorch.netmode.ntua.gr/ws/RSpec'

class FedericaManifest (PGv2):
    enabled = True
    type = 'Fedrica'
    content_type = 'manifest'
    schema = 'http://sorch.netmode.ntua.gr/ws/RSpec/manifest.xsd'
    namespace = 'http://sorch.netmode.ntua.gr/ws/RSpec'

