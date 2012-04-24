#
## (Re)builds Python metafile (__init__.py) 
# 
# overwritten by the specfile
DESTDIR="/"

##########
all: python wsdl 

install: python-install wsdl-install xmlbuilder-install tests-install

clean: python-clean wsdl-clean 

uninstall: python-uninstall tests-uninstall

.PHONY: all install clean uninstall

##########
rpmversion:=$(shell rpm -q --specfile sfa.spec --queryformat="%{version}\n" | head -1)
# somehow %{taglevel} is empty, turns out %{release} has what we want
rpmtaglevel:=$(shell rpm -q --specfile sfa.spec --queryformat="%{release}\n" 2> /dev/null | head -1)
VERSIONTAG=$(rpmversion)-$(rpmtaglevel)
SCMURL=should-be-redefined-by-specfile

python: version

version: sfa/util/version.py
sfa/util/version.py: sfa/util/version.py.in
	sed -e "s,@VERSIONTAG@,$(VERSIONTAG),g" -e "s,@SCMURL@,$(SCMURL),g" sfa/util/version.py.in > $@

xmlbuilder-install:
	cd xmlbuilder-0.9 && python setup.py install --root=$(DESTDIR) && cd -
	rm -rf $(DESTDIR)/usr/lib*/python*/site-packages/*egg-info

# postinstall steps - various cleanups and tweaks for a nicer rpm
python-install:
	python setup.py install --root=$(DESTDIR)	
	chmod 444 $(DESTDIR)/etc/sfa/default_config.xml
	rm -rf $(DESTDIR)/usr/lib*/python*/site-packages/*egg-info
	rm -rf $(DESTDIR)/usr/lib*/python*/site-packages/sfa/storage/migrations
	(cd $(DESTDIR)/usr/bin ; ln -s sfi.py sfi; ln -s sfascan.py sfascan)

python-clean: version-clean
	python setup.py clean
#	rm $(init)

version-clean:
	rm -f sfa/util/version.py

.PHONY: python version python-install python-clean version-clean xmlbuilder-install 
##########
wsdl: 
	$(MAKE) -C wsdl 

# propagate DESTDIR from the specfile
wsdl-install:
	$(MAKE) -C wsdl install 

wsdl-clean:
	$(MAKE) -C wsdl clean

.PHONY: wsdl wsdl-install wsdl-clean

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
scan:
	@find . -type f | egrep -v '^\./\.|/\.git/|/\.svn/|TAGS|AA-|~$$|egg-info|\.(py[co]|doc|html|pdf|png|svg|out|bak|dg|pickle)$$' 
tags:	
	$(MAKE) scan | xargs etags

.PHONY: scan tags

signatures:
	(cd sfa/methods; grep 'def.*call' *.py > SIGNATURES)
.PHONY: signatures

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
SSHURL:=root@$(PLCHOSTLXC):/var/lib/lxc/$(GUESTNAME)/rootfs
SSHCOMMAND:=ssh root@$(PLCHOSTLXC) ssh $(GUESTHOSTNAME)
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

CLIENTS = $(shell ls sfa/clientbin/*.py)

BINS =	./config/sfa-config-tty ./config/gen-sfa-cm-config.py \
	./sfa/server/sfa-start.py \
	./sfa/clientbin/sfaadmin.py \
	$(CLIENTS)

synclib: synccheck
	+$(RSYNC) --relative ./sfa/ --exclude migrations $(SSHURL)/usr/lib\*/python2.\*/site-packages/
syncbin: synccheck
	+$(RSYNC)  $(BINS) $(SSHURL)/usr/bin/
syncinit: synccheck
	+$(RSYNC) ./init.d/sfa  $(SSHURL)/etc/init.d/
syncconfig:
	+$(RSYNC) ./config/default_config.xml $(SSHURL)/etc/sfa/
synctest: synccheck
	+$(RSYNC) ./tests/ $(SSHURL)/root/tests-sfa
syncrestart: synccheck
	$(SSHCOMMAND) exec service sfa restart

syncmig:
	+$(RSYNC) ./sfa/storage/migrations $(SSHURL)/usr/share/sfa/


# full-fledged
sync: synclib syncbin syncinit syncconfig syncrestart
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
