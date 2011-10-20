# recompute the SFA graphs from different locations

SFASCAN = ./sfascan.py -v

# AMs, at least MyPLC AMs, are boring
#BUNDLES += http://planet-lab.eu:12346/@auto-ple-am
BUNDLES += http://planet-lab.eu:12345/@auto-ple-reg 
BUNDLES += http://planet-lab.eu:12347/@auto-ple-sa
BUNDLES += http://planet-lab.org:12345/@auto-plc-reg 
BUNDLES += http://planet-lab.org:12347/@auto-plc-sa
BUNDLES += http://planet-lab.kr:12345/@auto-ppk-reg 
BUNDLES += http://planet-lab.kr:12347/@auto-ppk-sa
BUNDLES += http://geni-myvini.umkc.gpeni.net:12345/@auto-gpeni-reg
BUNDLES += http://geni-myvini.umkc.gpeni.net:12347/@auto-gpeni-sa
BUNDLES += http://198.248.241.100:12345/@auto-glc-reg
BUNDLES += http://198.248.241.100:12347/@auto-glc-sa
BUNDLES += http://vini-veritas.net:12345/@auto-vini-reg
BUNDLES += http://vini-veritas.net:12347/@auto-vini-sa
BUNDLES += http://www.planet-lab.jp:12345/@auto-plj-reg 
BUNDLES += http://www.planet-lab.jp:12347/@auto-plj-sa
BUNDLES += http://www.emanicslab.org:12345/@auto-elc-reg 
BUNDLES += http://www.emanicslab.org:12347/@auto-elc-sa

# left to right
BUNDLES-LR += http://www.emulab.net:443/protogeni/xmlrpc/am/@auto-emulab-am
BUNDLES-LR += http://planet-lab.eu:12345/@auto-ple-reg 
BUNDLES-LR += http://planet-lab.eu:12347/@auto-ple-sa
BUNDLES-LR += http://planet-lab.org:12345/@auto-plc-reg 
BUNDLES-LR += http://planet-lab.org:12347/@auto-plc-sa
BUNDLES-LR += http://planet-lab.kr:12345/@auto-ppk-reg 
#BUNDLES-LR += http://planet-lab.kr:12347/@auto-ppk-sa
BUNDLES-LR += http://geni-myvini.umkc.gpeni.net:12345/@auto-gpeni-reg
BUNDLES-LR += http://geni-myvini.umkc.gpeni.net:12347/@auto-gpeni-sa
BUNDLES-LR += http://198.248.241.100:12345/@auto-glc-reg
BUNDLES-LR += http://198.248.241.100:12347/@auto-glc-sa
BUNDLES-LR += http://vini-veritas.net:12345/@auto-vini-reg
BUNDLES-LR += http://vini-veritas.net:12347/@auto-vini-sa
BUNDLES-LR += http://www.planet-lab.jp:12345/@auto-plj-reg 
BUNDLES-LR += http://www.planet-lab.jp:12347/@auto-plj-sa
BUNDLES-LR += http://www.emanicslab.org:12345/@auto-elc-reg 
BUNDLES-LR += http://www.emanicslab.org:12347/@auto-elc-sa

#EXTENSIONS := png svg
EXTENSIONS := png

####################
ALL += $(foreach bundle,$(BUNDLES),$(word 2,$(subst @, ,$(bundle))))
ALL += $(foreach bundle,$(BUNDLES-LR),$(word 2,$(subst @, ,$(bundle)))-lr)

all: $(ALL)

ple: auto-ple-reg auto-ple-sa-lr.out

####################
define bundle_scan_target
$(word 2,$(subst @, ,$(1))):
	$(SFASCAN) $(foreach extension,$(EXTENSIONS),-o $(word 2,$(subst @, ,$(1))).$(extension)) $(word 1,$(subst @, ,$(1))) >& .$(word 2,$(subst @, ,$(1))).out
.PHONY: $(word 2,$(subst @, ,$(1)))
endef

# the actual targets
$(foreach bundle,$(BUNDLES),$(eval $(call bundle_scan_target,$(bundle))))

#################### same but left-to-right
define bundle_scan_target_lr
$(word 2,$(subst @, ,$(1)))-lr:
	$(SFASCAN) -l $(foreach extension,$(EXTENSIONS),-o $(word 2,$(subst @, ,$(1)))-lr.$(extension)) $(word 1,$(subst @, ,$(1))) >& .$(word 2,$(subst @, ,$(1)))-lr.out
.PHONY: $(word 2,$(subst @, ,$(1)))-lr
endef

# the actual targets
$(foreach bundle,$(BUNDLES-LR),$(eval $(call bundle_scan_target_lr,$(bundle))))

####################
versions: $(VERSIONS)
clean-versions: 
	rm -f $(VERSIONS)

#################### make name.version
define bundle_version_target
$(word 2,$(subst @, ,$(1))).version:
	-./sfi.py -s $(word 1,$(subst @, ,$(1))) version >& $$@
endef

VERSIONS := $(foreach bundle,$(BUNDLES),$(word 2,$(subst @, ,$(bundle))).version)

# the actual targets
$(foreach bundle,$(BUNDLES),$(eval $(call bundle_version_target,$(bundle))))

####################
clean:
	rm -f auto-*.{out,version}
	$(foreach extension,$(EXTENSIONS),rm -rf auto-*.$(extension);)

DATE=$(shell date '+%Y-%m-%d')
PUBEXTENSIONS=png
publish:
	echo $(DATE)
	ssh tparment@srv-planete.inria.fr mkdir /proj/planete/www/Thierry.Parmentelat/sfascan/$(DATE)
	$(foreach extension,$(PUBEXTENSIONS),rsync -av auto-*.$(extension) tparment@srv-planete.inria.fr:/proj/planete/www/Thierry.Parmentelat/sfascan/$(DATE) ;)

#################### convenience, for debugging only
# make +foo : prints the value of $(foo)
# make ++foo : idem but verbose, i.e. foo=$(foo)
++%: varname=$(subst +,,$@)
++%:
	@echo "$(varname)=$($(varname))"
+%: varname=$(subst +,,$@)
+%:
	@echo "$($(varname))"
