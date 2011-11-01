#!/usr/bin/env python

import sys
import socket
import traceback
from urlparse import urlparse

import pygraphviz

from optparse import OptionParser

from sfa.client.sfi import Sfi
from sfa.util.sfalogging import logger, DEBUG
import sfa.client.xmlrpcprotocol as xmlrpcprotocol

def url_hostname_port (url):
    if url.find("://")<0:
        url="http://"+url
    parsed_url=urlparse(url)
    # 0(scheme) returns protocol
    default_port='80'
    if parsed_url[0]=='https': default_port='443'
    # 1(netloc) returns the hostname+port part
    parts=parsed_url[1].split(":")
    # just a hostname
    if len(parts)==1:
        return (url,parts[0],default_port)
    else:
        return (url,parts[0],parts[1])

###
class Interface:

    def __init__ (self,url):
        self._url=url
        try:
            (self._url,self.hostname,self.port)=url_hostname_port(url)
            self.ip=socket.gethostbyname(self.hostname)
            self.probed=False
        except:
            self.hostname="unknown"
            self.ip='0.0.0.0'
            self.port="???"
            # don't really try it
            self.probed=True
            self._version={}

    def url(self):
        return self._url

    # this is used as a key for creating graph nodes and to avoid duplicates
    def uid (self):
        return "%s:%s"%(self.ip,self.port)

    # connect to server and trigger GetVersion
    def get_version(self):
        if self.probed:
            return self._version
        # dummy to meet Sfi's expectations for its 'options' field
        class DummyOptions:
            pass
        options=DummyOptions()
        options.verbose=False
        options.timeout=10
        try:
            client=Sfi(options)
            client.read_config()
            key_file = client.get_key_file()
            cert_file = client.get_cert_file(key_file)
            url=self.url()
            logger.info('issuing get version at %s'%url)
            logger.debug("GetVersion, using timeout=%d"%options.timeout)
            server=xmlrpcprotocol.server_proxy(url, key_file, cert_file, timeout=options.timeout, verbose=options.verbose)
            self._version=server.GetVersion()
        except:
            self._version={}
        self.probed=True
        return self._version

    @staticmethod
    def multi_lines_label(*lines):
        result='<<TABLE BORDER="0" CELLBORDER="0"><TR><TD>' + \
            '</TD></TR><TR><TD>'.join(lines) + \
            '</TD></TR></TABLE>>'
        return result

    # default is for when we can't determine the type of the service
    # typically the server is down, or we can't authenticate, or it's too old code
    shapes = {"registry": "diamond", "slicemgr":"ellipse", "aggregate":"box", 'default':'plaintext'}
    abbrevs = {"registry": "REG", "slicemgr":"SA", "aggregate":"AM", 'default':'[unknown interface]'}

    # return a dictionary that translates into the node's attr
    def get_layout (self):
        layout={}
        ### retrieve cached GetVersion
        version=self.get_version()
        # set the href; xxx would make sense to try and 'guess' the web URL, not the API's one...
        layout['href']=self.url()
        ### set html-style label
        ### see http://www.graphviz.org/doc/info/shapes.html#html
        # if empty the service is unreachable
        if not version:
            label="offline"
        else:
            label=''
            try: abbrev=Interface.abbrevs[version['interface']]
            except: abbrev=Interface.abbrevs['default']
            label += abbrev
            if 'hrn' in version: label += " %s"%version['hrn']
            else:                label += "[no hrn]"
            if 'code_tag' in version: 
                label += " %s"%version['code_tag']
            if 'testbed' in version:
                label += " (%s)"%version['testbed']
        layout['label']=Interface.multi_lines_label(self.url(),label)
        ### set shape
        try: shape=Interface.shapes[version['interface']]
        except: shape=Interface.shapes['default']
        layout['shape']=shape
        ### fill color to outline wrongly configured bodies
        if 'geni_api' not in version and 'sfa' not in version:
            layout['style']='filled'
            layout['fillcolor']='gray'
        return layout

class SfaScan:

    # provide the entry points (a list of interfaces)
    def __init__ (self, left_to_right=False, verbose=False):
        self.verbose=verbose
        self.left_to_right=left_to_right

    def graph (self,entry_points):
        graph=pygraphviz.AGraph(directed=True)
        if self.left_to_right: 
            graph.graph_attr['rankdir']='LR'
        self.scan(entry_points,graph)
        return graph
    
    # scan from the given interfaces as entry points
    def scan(self,interfaces,graph):
        if not isinstance(interfaces,list):
            interfaces=[interfaces]

        # remember node to interface mapping
        node2interface={}
        # add entry points right away using the interface uid's as a key
        to_scan=interfaces
        for i in interfaces: 
            graph.add_node(i.uid())
            node2interface[graph.get_node(i.uid())]=i
        scanned=[]
        # keep on looping until we reach a fixed point
        # don't worry about abels and shapes that will get fixed later on
        while to_scan:
            for interface in to_scan:
                # performing xmlrpc call
                version=interface.get_version()
                if self.verbose:
                    logger.info("GetVersion at interface %s"%interface.url())
                    if not version:
                        logger.info("<EMPTY GetVersion(); offline or cannot authenticate>")
                    else: 
                        for (k,v) in version.iteritems(): 
                            if not isinstance(v,dict):
                                logger.info("\r\t%s:%s"%(k,v))
                            else:
                                logger.info(k)
                                for (k1,v1) in v.iteritems():
                                    logger.info("\r\t\t%s:%s"%(k1,v1))
                # 'geni_api' is expected if the call succeeded at all
                # 'peers' is needed as well as AMs typically don't have peers
                if 'geni_api' in version and 'peers' in version: 
                    # proceed with neighbours
                    for (next_name,next_url) in version['peers'].iteritems():
                        next_interface=Interface(next_url)
                        # locate or create node in graph
                        try:
                            # if found, we're good with this one
                            next_node=graph.get_node(next_interface.uid())
                        except:
                            # otherwise, let's move on with it
                            graph.add_node(next_interface.uid())
                            next_node=graph.get_node(next_interface.uid())
                            node2interface[next_node]=next_interface
                            to_scan.append(next_interface)
                        graph.add_edge(interface.uid(),next_interface.uid())
                scanned.append(interface)
                to_scan.remove(interface)
            # we've scanned the whole graph, let's get the labels and shapes right
            for node in graph.nodes():
                interface=node2interface.get(node,None)
                if interface:
                    for (k,v) in interface.get_layout().iteritems():
                        node.attr[k]=v
                else:
                    logger.error("MISSED interface with node %s"%node)
    

default_outfiles=['sfa.png','sfa.svg','sfa.dot']

def main():
    usage="%prog [options] url-entry-point(s)"
    parser=OptionParser(usage=usage)
    parser.add_option("-o","--output",action='append',dest='outfiles',default=[],
                      help="output filenames (cumulative) - defaults are %r"%default_outfiles)
    parser.add_option("-l","--left-to-right",action="store_true",dest="left_to_right",default=False,
                      help="instead of top-to-bottom")
    parser.add_option("-v","--verbose",action='store_true',dest='verbose',default=False,
                      help="verbose")
    parser.add_option("-d","--debug",action='store_true',dest='debug',default=False,
                      help="debug")
    (options,args)=parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(1)
    if not options.outfiles:
        options.outfiles=default_outfiles
    logger.enable_console()
    if options.debug:
        options.verbose=True
        logger.setLevel(DEBUG)
    scanner=SfaScan(left_to_right=options.left_to_right, verbose=options.verbose)
    entries = [ Interface(entry) for entry in args ]
    g=scanner.graph(entries)
    logger.info("creating layout")
    g.layout(prog='dot')
    for outfile in options.outfiles:
        logger.info("drawing in %s"%outfile)
        g.draw(outfile)
    logger.info("done")

if __name__ == '__main__':
    main()
