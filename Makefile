#
## (Re)builds Python metafile (__init__.py) 
# 
# overwritten by the specfile
DESTDIR="/"
PREFIX=/usr
##########
all: python wsdl 

install: python-install wsdl-install tests-install

clean: python-clean wsdl-clean 

uninstall: python-uninstall tests-uninstall

.PHONY: all install clean uninstall

##########
rpmversion:=$(shell rpm -q --specfile sfa.spec --queryformat="%{version}\n" | head -1)
# somehow %{taglevel} is empty, turns out %{release} has what we want
rpmtaglevel:=$(shell rpm -q --specfile sfa.spec --queryformat="%{release}\n" 2> /dev/null | head -1)
VERSIONTAG=$(rpmversion)-$(rpmtaglevel)
# this used to be 'should-be-redefined-by-specfile' and it indeed should be
SCMURL=git://git.onelab.eu/sfa.git

python: version

version: sfa/util/version.py 
sfa/util/version.py: sfa/util/version.py.in force
	sed -e "s,@VERSIONTAG@,$(VERSIONTAG),g" -e "s,@SCMURL@,$(SCMURL),g" sfa/util/version.py.in > $@

# postinstall steps - various cleanups and tweaks for a nicer rpm
python-install:
	python setup.py install --prefix=$(PREFIX) --root=$(DESTDIR)
	chmod 444 $(DESTDIR)/etc/sfa/default_config.xml
	rm -rf $(DESTDIR)/usr/lib*/python*/site-packages/*egg-info
	rm -rf $(DESTDIR)/usr/lib*/python*/site-packages/sfa/storage/migrations
	(cd $(DESTDIR)/usr/bin ; ln -s sfi.py sfi; ln -s sfascan.py sfascan; ln -s sfaadmin.py sfaadmin)

python-clean: version-clean
	python setup.py clean
#	rm $(init)

version-clean:
	rm -f sfa/util/version.py

.PHONY: python version python-install python-clean version-clean 
##########
wsdl: 
	$(MAKE) -C wsdl 

# propagate DESTDIR from the specfile
wsdl-install:
	$(MAKE) -C wsdl install 

wsdl-clean:
	$(MAKE) -C wsdl clean

.PHONY: wsdl wsdl-install wsdl-clean

######################################## debian packaging
# The 'debian' target is called from the build with the following variables set 
# (see build/Makefile and target_debian)
# (.) RPMTARBALL
# (.) RPMVERSION
# (.) RPMRELEASE
# (.) RPMNAME
#
PROJECT=$(RPMNAME)
DEBVERSION=$(RPMVERSION).$(RPMRELEASE)
DEBTARBALL=../$(PROJECT)_$(DEBVERSION).orig.tar.bz2

DATE=$(shell date -u +"%a, %d %b %Y %T")

debian: debian/changelog debian.source debian.package

debian/changelog: debian/changelog.in
	sed -e "s|@VERSION@|$(DEBVERSION)|" -e "s|@DATE@|$(DATE)|" debian/changelog.in > debian/changelog

debian.source: force 
	rsync -a $(RPMTARBALL) $(DEBTARBALL)

debian.package:
	debuild -uc -us -b 

debian.clean:
	$(MAKE) -f debian/rules clean
	rm -rf build/ MANIFEST ../*.tar.gz ../*.dsc ../*.build
	find . -name '*.pyc' -delete

##########
tests-install:
	mkdir -p $(DESTDIR)/usr/share/sfa/tests
	install -m 755 tests/*.py $(DESTDIR)/usr/share/sfa/tests/

tests-uninstall:
	rm -rf $(DESTDIR)/usr/share/sfa/tests

.PHONY: tests-install tests-uninstall

########## refreshing methods package metafile
# Metafiles - manage Legacy/ and Accessors by hand
init := sfa/methods/__init__.py 

index: $(init)

index-clean:
	rm $(init)

methods_now := $(sort $(shell fgrep -v '"' sfa/methods/__init__.py 2>/dev/null))
# what should be declared
methods_paths := $(filter-out %/__init__.py, $(wildcard sfa/methods/*.py))
methods_files := $(sort $(notdir $(methods_paths:.py=)))

ifneq ($(methods_now),$(methods_files))
sfa/methods/__init__.py: force
endif
sfa/methods/__init__.py: 
	(echo '## Please use make index to update this file' ; echo 'all = """' ; cd sfa/methods; ls -1 *.py | grep -v __init__ | sed -e 's,.py$$,,' ; echo '""".split()') > $@

force:

##########
# a lot of stuff in the working dir is just noise
files:
	@find . -type f | egrep -v '^\./\.|/\.git/|/\.svn/|TAGS|AA-|~$$|egg-info|\.(py[co]|doc|html|pdf|png|svg|out|bak|dg|pickle)$$' 

git-files:
	@git ls-files | grep -v '\.doc$$'

tags:	
	$(MAKE) git-files | xargs etags

.PHONY: files tags

signatures:
	(cd sfa/methods; grep 'def.*call' *.py > SIGNATURES)
.PHONY: signatures

########## for uploading onto pypi
# use pypitest instead for tests (both entries need to be defined in your .pypirc)
PYPI_TARGET=pypi
PYPI_TARBALL_HOST=root@build.onelab.eu
PYPI_TARBALL_TOPDIR=/build/sfa

# a quick attempt on pypitest did not quite work as expected
# I was hoping to register the project using "setup.py register"
# but somehow most of my meta data did not make it up there
# and I could not find out why
# so I went for the manual method instead
# there also was a web dialog prompting for a zip file that would
# be used to initialize the project's home dir but this too 
# did not seem to work the way I was trying to use it, so ...

# this target is still helpful to produce the readme in html from README.md
index.zip index.html: README.md
	python readme.py

# I need to run this on my mac as my pypi
# run git pull first as this often comes afet a module-tag
# we need to re-run make so the version is right
git_pypi: git pypi

git: 
	git pull
	$(MAKE) version

# run this only once the sources are in on the right tag
pypi: index.html
	setup.py sdist upload -r $(PYPI_TARGET)
	ssh $(PYPI_TARBALL_HOST) mkdir -p $(PYPI_TARBALL_TOPDIR)/$(VERSIONTAG)
	rsync -av dist/sfa-$(VERSIONTAG).tar.gz $(PYPI_TARBALL_HOST):$(PYPI_TARBALL_TOPDIR)/$(VERSIONTAG)

# cleanup
clean: readme-clean

readme-clean:
	rm -f index.html index.zip

########## sync
# 2 forms are supported
# (*) if your plc root context has direct ssh access:
# make sync PLC=private.one-lab.org
# (*) otherwise, for test deployments, use on your testmaster
# $ run export
# and cut'n paste the export lines before you run make sync

ifdef PLC
SSHURL:=root@$(PLC):/
SSHCOMMAND:=ssh root@$(PLC)
else
ifdef PLCHOSTLXC
SSHURL:=root@$(PLCHOSTLXC):/vservers/$(GUESTNAME)
SSHCOMMAND:=ssh root@$(PLCHOSTLXC) virsh -c lxc:/// lxc-enter-namespace $(GUESTNAME) -- /usr/bin/env
else
ifdef PLCHOSTVS
SSHURL:=root@$(PLCHOSTVS):/vservers/$(GUESTNAME)
SSHCOMMAND:=ssh root@$(PLCHOSTVS) vserver $(GUESTNAME) exec
endif
endif
endif

synccheck: 
ifeq (,$(SSHURL))
	@echo "sync: I need more info from the command line, e.g."
	@echo "  make sync PLC=boot.planetlab.eu"
	@echo "  make sync PLCHOSTVS=.. GUESTNAME=.."
	@echo "  make sync PLCHOSTLXC=.. GUESTNAME=.. GUESTHOSTNAME=.."
	@exit 1
endif

LOCAL_RSYNC_EXCLUDES	+= --exclude '*.pyc' 
LOCAL_RSYNC_EXCLUDES	+= --exclude '*.png' --exclude '*.svg' --exclude '*.out'
RSYNC_EXCLUDES		:= --exclude .svn --exclude .git --exclude '*~' --exclude TAGS $(LOCAL_RSYNC_EXCLUDES)
RSYNC_COND_DRY_RUN	:= $(if $(findstring n,$(MAKEFLAGS)),--dry-run,)
RSYNC			:= rsync -a -v $(RSYNC_COND_DRY_RUN) --no-owner $(RSYNC_EXCLUDES)

CLIENTS = $(shell ls clientbin/*.py)

BINS =	./config/sfa-config-tty ./config/gen-sfa-cm-config.py \
	./sfa/server/sfa-start.py \
	./clientbin/sfaadmin.py \
	$(CLIENTS)

synclib: synccheck
	+$(RSYNC) --relative ./sfa/ --exclude migrations $(SSHURL)/usr/lib\*/python2.\*/site-packages/
synclibdeb: synccheck
	+$(RSYNC) --relative ./sfa/ --exclude migrations $(SSHURL)/usr/share/pyshared/
syncbin: synccheck
	+$(RSYNC)  $(BINS) $(SSHURL)/usr/bin/
syncinit: synccheck
	+$(RSYNC) ./init.d/sfa  $(SSHURL)/etc/init.d/
syncconfig:
	+$(RSYNC) ./config/default_config.xml $(SSHURL)/etc/sfa/
synctest: synccheck
	+$(RSYNC) ./tests/ $(SSHURL)/root/tests-sfa
syncrestart: synccheck
	-$(SSHCOMMAND) systemctl --system daemon-reload
	$(SSHCOMMAND) service sfa restart

syncmig:
	+$(RSYNC) ./sfa/storage/migrations $(SSHURL)/usr/share/sfa/


# full-fledged
sync: synclib syncbin syncinit syncconfig syncrestart
syncdeb: synclibdeb syncbin syncinit syncconfig syncrestart
# 99% of the time this is enough
syncfast: synclib syncrestart

.PHONY: synccheck synclib syncbin syncconfig synctest syncrestart sync syncfast

##########
CLIENTLIBFILES= \
sfa/examples/miniclient.py \
sfa/__init__.py \
sfa/client/{sfaserverproxy,sfaclientlib,__init__}.py \
sfa/trust/{certificate,__init__}.py \
sfa/util/{sfalogging,faults,genicode,enumeration,__init__}.py 

clientlibsync: 
	@[ -d "$(CLIENTLIBTARGET)" ] || { echo "You need to set the make variable CLIENTLIBTARGET"; exit 1; }
	rsync -av --relative $(CLIENTLIBFILES) $(CLIENTLIBTARGET)

#################### convenience, for debugging only
# make +foo : prints the value of $(foo)
# make ++foo : idem but verbose, i.e. foo=$(foo)
++%: varname=$(subst +,,$@)
++%:
	@echo "$(varname)=$($(varname))"
+%: varname=$(subst +,,$@)
+%:
	@echo "$($(varname))"
