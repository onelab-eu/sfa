#
# $Id$
#

%define url $URL$

%define name sfa
%define version 0.9
%define taglevel 15

%define release %{taglevel}%{?pldistro:.%{pldistro}}%{?date:.%{date}}
%global python_sitearch	%( python -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)" )
%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.bz2
License: GPL
Group: Applications/System
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot

Vendor: PlanetLab
Packager: PlanetLab Central <support@planet-lab.org>
Distribution: PlanetLab %{plrelease}
URL: %(echo %{url} | cut -d ' ' -f 2)
Summary: the SFA python libraries
Group: Applications/System

BuildRequires: make
Requires: python >= 2.5
Requires: m2crypto
Requires: xmlsec1-openssl-devel
Requires: libxslt-python
Requires: python-ZSI
# xmlbuilder depends on  lxml
Requires: python-lxml
Requires: python-setuptools
Requires: python-dateutil
 
# python 2.5 has uuid module added, for python 2.4 we still need it.
# we can't really check for if we can load uuid as a python module,
# it'll be installed by "devel.pkgs". we have the epel repository so
# python-uuid will be provided. but we can test for the python
# version.
# %define has_py24 %( python -c "import sys;sys.exit(sys.version_info[0:2] == (2,4))" 2> /dev/null; echo $? )
# %if %has_py24
#
# this also didn't work very well. I'll just check for distroname - baris
%if %{distroname} == "centos5"
Requires: python-uuid
%endif

%package cm
Summary: the SFA wrapper around MyPLC's NodeManager
Group: Applications/System
Requires: sfa
Requires: pyOpenSSL >= 0.6

%package plc
Summary: the SFA wrapper arounf MyPLC
Group: Applications/System
Requires: sfa
Requires: python-psycopg2
Requires: myplc-config
Requires: pyOpenSSL >= 0.7

%package client
Summary: the SFA experimenter-side CLI
Group: Applications/System
Requires: sfa
Requires: pyOpenSSL >= 0.7

%package sfatables
Summary: sfatables policy tool for SFA
Group: Applications/System
Requires: sfa

%description
This package provides the python libraries that the SFA implementation requires

%description cm
This package implements the SFA interface which serves as a layer
between the existing PlanetLab NodeManager interfaces and the SFA API.
 
%description plc
This package implements the SFA interface which serves as a layer
between the existing PlanetLab interfaces and the SFA API.

%description client
This package provides the client side of the SFA API, in particular
sfi.py, together with other utilities.

%description sfatables
sfatables is a tool for defining access and admission control policies
in an SFA network, in much the same way as iptables is for ip
networks. This is the command line interface to manage sfatables

%prep
%setup -q

%build
make

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR="$RPM_BUILD_ROOT"

%clean
rm -rf $RPM_BUILD_ROOT

%files
# sfa and sfatables depend each other.
%{_bindir}/sfa-server.py*
/etc/sfatables/*
%{python_sitelib}/*
%{_bindir}/keyconvert.py*
/var/www/html/wsdl/*.wsdl

%files cm
/etc/init.d/sfa-cm
%{_bindir}/sfa_component_setup.py*
# cron jobs here 

%files plc
%defattr(-,root,root)
%config /etc/sfa/default_config.xml
%config (noreplace) /etc/sfa/aggregates.xml
%config (noreplace) /etc/sfa/registries.xml
/etc/init.d/sfa
/etc/sfa/pl.rng
%{_bindir}/sfa-config-tty
%{_bindir}/sfa-import-plc.py*
%{_bindir}/sfa-clean-peer-records.py*
%{_bindir}/sfa-nuke-plc.py*
%{_bindir}/gen-sfa-cm-config.py*
%{_bindir}/sfa-ca.py*

%files client
%config (noreplace) /etc/sfa/sfi_config
%{_bindir}/sfi*
%{_bindir}/getNodes.py*
%{_bindir}/getRecord.py*
%{_bindir}/setRecord.py*
%{_bindir}/sfadump.py*

%files sfatables
%{_bindir}/sfatables

%pre plc
[ -f %{_sysconfdir}/init.d/sfa ] && service sfa stop ||:

%pre cm
[ -f %{_sysconfdir}/init.d/sfa-cm ] && service sfa-cm stop ||:

%post plc
chkconfig --add sfa

%post cm
chkconfig --add sfa-cm
%changelog
* Thu May 11 2010 Tony Mack <tmack@cs.princeton.edu> - sfa-0.9-11
- SfaServer now uses a pool of threads to handle requests concurrently
- sfa.util.rspec no longer used to process/manage rspecs (deprecated). This is now handled by sfa.plc.network and is not backwards compatible
- PIs can now get a slice credential for any slice at their site without having to be a member of the slice
- Registry records for federated peers (defined in registries.xml, aggregates.xml) updated when sfa service is started
- Interfaces will try to fetch and install gids from peers listed in registries.xml/aggregates.xml if gid is not found in /etc/sfa/trusted_roots dir   
- Component manager does not install gid files if slice already has them  
- Server automatically fetches and installs peer certificats (defined in registries/aggregates.xml) when service is restarted.
- fix credential verification exploit (verify that the trusted signer is a parent of the object it it signed)
- made it easier for root authorities to sign their sub's certifiacate using the sfa-ca.py (sfa/server/sfa-ca.py) tool
     
* Thu Jan 21 2010 anil vengalil <avengali@sophia.inria.fr> - sfa-0.9-10
- This tag is quite same as the previous one (sfa-0.9-9) except that the vini and max aggregate managers are also updated for urn support.  Other features are:
- - sfa-config-tty now has the same features like plc-config-tty
- - Contains code to support both urn and hrn
- - Cleaned up request_hash related stuff
- - SM, AM and Registry code is organized under respective managers
- - Site and Slice synchronization across federated aggregates
- - Script to generate sfa_component_config

* Fri Jan 15 2010 anil vengalil <avengali@sophia.inria.fr> - sfa-0.9-9
- sfa-config-tty now has the same features like plc-config-tty
- Contains code to support both urn and hrn
- Cleaned up request_hash related stuff
- SM, AM and Registry code is organized under respective managers
- Slice synchronization across federated aggregates
- some bugs are fixed

* Wed Jan 06 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - sfa-0.9-8
- checkpoint with fewer mentions of geni

* Tue Jan 05 2010 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - sfa-0.9-7
- checkpointing
- this is believed to pass the tests; among other things:
- reworked configuration based on the myplc config with xml skeleton (no more sfa_config)

* Mon Nov 16 2009 anil vengalil <avengali@sophia.inria.fr> - sfa-0.9-6
- This tag includes:
- - Sfatables
- - Preliminary version of hash based authentication
- - Initial code for Component Manager
- - Authority structure is moved to /var/lib/sfa/
- - some bug-fixes

* Fri Oct 09 2009 anil vengalil <avengali@sophia.inria.fr> - sfa-0.9-5
- Create_slice and get_resources methods are connected to sfatables.
- Other features include compatibility with RP, handling remote objects created as part of federation, preliminary version of sfatables, call tracability and logging.

* Wed Oct 07 2009 anil vengalil <avengali@sophia.inria.fr> - sfa-0.9-4
- Bug fix on update and remove_peer_object methods
- Compatibility with RP, preliminiary version of sfatables, call tracability and logging

* Mon Oct 05 2009 anil vengalil <avengali@sophia.inria.fr> - sfa-0.9-3
- Compatibility with RP, two additional methods to handle remote objects, call tracability and logging, PLCDB now has single table for sfa records, preliminary version of sfatables (still under development)

* Fri Sep 18 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - sfa-0.9-2
- compatibility with RefreshPeer
- incremental mechanism for importing PLC records into SFA tables
- unified single database (still inside the underlying PLC db postgresql server)
- includes/improves call traceability and logging features
- several bug fixes

* Thu Sep 17 2009 Baris Metin <tmetin@sophia.inria.fr>
- added libxslt-python dependency

* Thu Sep 10 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - sfa-0.9-1
- unified single SFA database in the PLC-DB
- upcalls from  PLCAPI to SFA methods
- SFA call traceability and logging features
- many bug fixes
- includes first/rough version of sfatables for policy implementation

* Thu Jul 23 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.8-6
- snapshot after the GEC5 demo
- should be the last tag set in the geniwrapper module, are we are now moving to the sfa module

* Wed Jul 15 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.8-5
- snapshot july 15 - has gone through superficial manual testing
- hopefully a good basis for gec5 demo
- multi-dir sfi client tested as well

* Wed Jul 08 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.8-4
- rename geniwrapper.spec into sfa.spec

* Wed Jul 08 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.8-3
- clean up in xmlrpc/soap, --protocol option to chose between both
- keyconvert packaged in /usr/bin, no /usr/share/keyconvert anymore
- hopefully more helpful context in case of crashes when importing
- bugfixes for using only /etc/sfa for site-dep files
- bugfixes in wsdl generation

* Mon Jul 06 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.8-2
- cleanup of the config area; no dependency to a PLC config anymore as sfa can be run in standalone
- config variables in sfa_config now start with SFA_ and not GENI_
- config.py can be loaded even with no config present

* Sun Jul 05 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.8-1
- first step for cleanup and reorganization
- mass-renaming from geni to sfa (some are still needed)
- sfa/trust implements the security architecture

* Wed Jul 01 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.2-7
- snapshot for reproducible builds

* Thu Jun 25 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.2-6
- snapshot for the convenience of alpha users

* Tue Jun 16 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.2-5
- build fix - keyconvert was getting installed in /usr/share/keyconvert/keyconvert

* Tue Jun 16 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.2-4
- ongoing work - snapshot for 4.3-rc9

* Wed Jun 03 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.2-3
- various fixes

* Sat May 30 2009 Thierry Parmentelat <thierry.parmentelat@sophia.inria.fr> - geniwrapper-0.2-2
- bugfixes - still a work in progress

* Fri May 18 2009 Baris Metin <tmetin@sophia.inria.fr>
- initial package


%define module_current_branch 0.2
