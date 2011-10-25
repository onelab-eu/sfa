########## compute dependency graphs
DEPTOOLS=py2depgraph.py depgraph2dot.py

all:deps

deps: server.png client.png

server.dg: $(DEPTOOLS)
	py2depgraph.py ../sfa/server/sfa-server.py > $@

client.dg: $(DEPTOOLS)
	py2depgraph.py ../sfa/client/sfi.py > $@

%.png: %.dg
	depgraph2dot.py < $*.dg | dot -T png -o $*.png

clean: 
	rm -f *png *dg
