from sfa.rspecs.sfa_rspec import sfa_rspec_version
from sfa.rspecs.pg_rspec import pg_rspec_ad_version, pg_rspec_request_version 

ad_rspec_versions = [
    pg_rspec_ad_version,
    sfa_rspec_version
    ]

request_rspec_versions = ad_rspec_versions

default_rspec_version = { 'type': 'SFA', 'version': '1' }

supported_rspecs = {'ad_rspec_versions': ad_rspec_versions,
                    'request_rspec_versions': request_rspec_versions,
                    'default_ad_rspec': default_rspec_version}

