#!/usr/bin/python
#
# Sapan Bhatia <sapanb@cs.princeton.edu>
#
# Generates a WSDL for sfa


import os, sys
import time
import pdb
import xml.dom.minidom
import xml.dom.ext
import apistub
import inspect

from types import *
from optparse import OptionParser

from sfa.util.parameter import Parameter,Mixed

import globals

class SoapError(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)
try:
    set
except NameError:
    from sets import Set
    set = Set

class WSDLGen:
    complex_types = {}
    services = {}
    num_types = 0
    wsdl = None
    types = None

    def __init__(self, interface_options):
        self.interface_options = interface_options

    def filter_argname(self,argname):
        if (not self.interface_options.lite or (argname!="cred")):
            if (argname.find('(') != -1):
                # The name has documentation in it :-/
                brackright = argname.split('(')[1]
                if (brackright.find(')') == -1):
                        raise Exception("Please fix the argument %s to be well-formed.\n"%argname)
                inbrack = brackright.split(')')[0]
                argname = inbrack
        return argname

    def fold_complex_type_names(self,acc, arg):
        name = arg.doc
        if (type(acc)==list):
            acc.append(name)
        else:
            p_i_b = acc.doc
            acc = [p_i_b,name]
        return acc

    def fold_complex_type(self,acc, arg):
        name = self.name_complex_type(arg)
        self.complex_types[arg]=name
        if (type(acc)==list):
            acc.append(name)
        else:
            p_i_b = self.name_complex_type(acc)
            acc = [p_i_b,name]
        return acc

    def name_complex_type(self,arg):

        types_section = self.types.getElementsByTagName("xsd:schema")[0]

        #pdb.set_trace()
        if (isinstance(arg, Mixed)):
            inner_types = reduce(self.fold_complex_type, arg)
            inner_names = reduce(self.fold_complex_type_names, arg)
            if (inner_types[-1]=="none"):
                inner_types=inner_types[:-1]
                min_args = 0
            else:
                min_args = 1
        
            self.num_types=self.num_types+1
            type_name = "Type%d"%self.num_types
            complex_type = types_section.appendChild(self.types.createElement("xsd:complexType"))
            complex_type.setAttribute("name", type_name)

            choice = complex_type.appendChild(self.types.createElement("xsd:choice"))
            for n,t in zip(inner_names,inner_types):
                element = choice.appendChild(self.types.createElement("element"))
                n = self.filter_argname(n)
                element.setAttribute("name", n)
                element.setAttribute("type", "%s"%t)
                element.setAttribute("minOccurs","%d"%min_args)
            return "xsdl:%s"%type_name
        elif (isinstance(arg, Parameter)):
            return (self.name_simple_type(arg.type))
        elif type(arg) == ListType or type(arg) == TupleType:
            inner_type = self.name_complex_type(arg[0]) 
            self.num_types=self.num_types+1
            type_name = "Type%d"%self.num_types
            complex_type = types_section.appendChild(self.types.createElement("xsd:complexType"))
            type_name = self.filter_argname(type_name)
            complex_type.setAttribute("name", type_name)
            complex_content = complex_type.appendChild(self.types.createElement("xsd:complexContent"))
            restriction = complex_content.appendChild(self.types.createElement("xsd:restriction"))
            restriction.setAttribute("base","soapenc:Array")
            attribute = restriction.appendChild(self.types.createElement("xsd:attribute"))
            attribute.setAttribute("ref","soapenc:arrayType")
            attribute.setAttribute("wsdl:arrayType","%s[]"%inner_type)

            return "xsdl:%s"%type_name

        elif type(arg) == DictType or arg == DictType or (inspect.isclass(arg) and issubclass(arg, dict)):
            self.num_types=self.num_types+1
            type_name = "Type%d"%self.num_types
            complex_type = types_section.appendChild(self.types.createElement("xsd:complexType"))
            type_name = self.filter_argname(type_name)
            complex_type.setAttribute("name", type_name)
            complex_content = complex_type.appendChild(self.types.createElement("xsd:sequence"))
     
            for k in arg.fields:
                inner_type = self.name_complex_type(arg.fields[k]) 
                element=complex_content.appendChild(self.types.createElement("xsd:element"))
                element.setAttribute("name",k)
                element.setAttribute("type",inner_type)

            return "xsdl:%s"%type_name 
        else:
            return (self.name_simple_type(arg))

    def name_simple_type(self,arg_type):
        # A Parameter is reported as an instance, even though it is serialized as a type <>
        if type(arg_type) == InstanceType:
            return (self.name_simple_type(arg_type.type))
        if arg_type == None:
            return "none"
        if arg_type == DictType:
            return "xsd:anyType"
        if arg_type in (ListType, TupleType):
            return "xsd:arrayType"
        elif arg_type == IntType or arg_type == LongType:
            return "xsd:int"
        elif arg_type == bool:
            return "xsd:boolean"
        elif arg_type == FloatType:
            return "xsd:double"
        elif arg_type in StringTypes:
            return "xsd:string"
        else:
           pdb.set_trace()
           raise SoapError, "Cannot handle %s objects" % arg_type

    def param_type(self, arg):
        return (self.name_complex_type(arg))

    def add_wsdl_ports_and_bindings (self):
        for method in apistub.methods:

            # Skip system. methods
            if "system." in method:
                continue

            function = apistub.callable(method) # Commented documentation
            #lines = ["// " + line.strip() for line in function.__doc__.strip().split("\n")]
            #print "\n".join(lines)
            #print

            
            in_el = self.wsdl.firstChild.appendChild(self.wsdl.createElement("message"))
            in_el.setAttribute("name", method + "_in")

            for service_name in function.interfaces:
                if (self.services.has_key(service_name)):
                    if (not method in self.services[service_name]):
                        self.services[service_name].append(method)
                else:
                    self.services[service_name]=[method]

            # Arguments

            if (function.accepts):
                (min_args, max_args, defaults) = function.args()
                for (argname,argtype) in zip(max_args,function.accepts):
                    argname = self.filter_argname(argname)
                    arg_part = in_el.appendChild(self.wsdl.createElement("part"))
                    arg_part.setAttribute("name", argname)
                    arg_part.setAttribute("type", self.param_type(argtype))
                    
            # Return type            
            return_type = function.returns
            out_el = self.wsdl.firstChild.appendChild(self.wsdl.createElement("message"))
            out_el.setAttribute("name", method + "_out")
            ret_part = out_el.appendChild(self.wsdl.createElement("part"))
            ret_part.setAttribute("name", "Result")
            ret_part.setAttribute("type", self.param_type(return_type))

            # Port connecting arguments with return type

            port_el = self.wsdl.firstChild.appendChild(self.wsdl.createElement("portType"))
            port_el.setAttribute("name", method + "_port")
            
            op_el = port_el.appendChild(self.wsdl.createElement("operation"))
            op_el.setAttribute("name", method)
            inp_el=self.wsdl.createElement("input")
            inp_el.setAttribute("message","tns:" + method + "_in")
            inp_el.setAttribute("name",method+"_request")
            op_el.appendChild(inp_el)
            out_el = self.wsdl.createElement("output")
            out_el.setAttribute("message","tns:" + method + "_out")
            out_el.setAttribute("name",method+"_response")
            op_el.appendChild(out_el)

            # Bindings

            bind_el = self.wsdl.firstChild.appendChild(self.wsdl.createElement("binding"))
            bind_el.setAttribute("name", method + "_binding")
            bind_el.setAttribute("type", "tns:" + method + "_port")
            
            soap_bind = bind_el.appendChild(self.wsdl.createElement("soap:binding"))
            soap_bind.setAttribute("style", "rpc")
            soap_bind.setAttribute("transport","http://schemas.xmlsoap.org/soap/http")

            
            wsdl_op = bind_el.appendChild(self.wsdl.createElement("operation"))
            wsdl_op.setAttribute("name", method)
            wsdl_op.appendChild(self.wsdl.createElement("soap:operation")).setAttribute("soapAction",
                    "urn:" + method)

            
            wsdl_input = wsdl_op.appendChild(self.wsdl.createElement("input"))
            input_soap_body = wsdl_input.appendChild(self.wsdl.createElement("soap:body"))
            input_soap_body.setAttribute("use", "encoded")
            input_soap_body.setAttribute("namespace", "urn:" + method)
            input_soap_body.setAttribute("encodingStyle","http://schemas.xmlsoap.org/soap/encoding/")

            
            wsdl_output = wsdl_op.appendChild(self.wsdl.createElement("output"))
            output_soap_body = wsdl_output.appendChild(self.wsdl.createElement("soap:body"))
            output_soap_body.setAttribute("use", "encoded")
            output_soap_body.setAttribute("namespace", "urn:" + method)
            output_soap_body.setAttribute("encodingStyle","http://schemas.xmlsoap.org/soap/encoding/")
            

    def add_wsdl_services(self):
        for service in self.services.keys():
            if (getattr(self.interface_options,service)):
                service_el = self.wsdl.firstChild.appendChild(self.wsdl.createElement("service"))
                service_el.setAttribute("name", service)

                for method in self.services[service]:
                        name=method
                        servport_el = service_el.appendChild(self.wsdl.createElement("port"))
                        servport_el.setAttribute("name", name + "_port")
                        servport_el.setAttribute("binding", "tns:" + name + "_binding")

                        soapaddress = servport_el.appendChild(self.wsdl.createElement("soap:address"))
                        soapaddress.setAttribute("location", "%s/%s" % (globals.plc_ns,service))


    def compute_wsdl_definitions(self):
        wsdl_text_header = """
            <wsdl:definitions
            name="sfa_autogenerated"
            targetNamespace="%s/2009/07/sfa.wsdl"
            xmlns="http://schemas.xmlsoap.org/wsdl/"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xsdl="%s/2009/07/schema"
            xmlns:tns="%s/2009/07/sfa.wsdl"
            xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
            xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
            xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"/>
            """ % (globals.plc_ns,globals.plc_ns,globals.plc_ns)
            
        self.wsdl = xml.dom.minidom.parseString(wsdl_text_header)
        

    def compute_wsdl_definitions_and_types(self):
        wsdl_text_header = """
        <wsdl:definitions
            name="sfa_autogenerated"
            targetNamespace="%s/2009/07/sfa.wsdl"
            xmlns="http://schemas.xmlsoap.org/wsdl/"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xsdl="%s/2009/07/schema"
            xmlns:tns="%s/2009/07/sfa.wsdl"
            xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
            xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
            xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/">
            <types>
                <xsd:schema xmlns="http://www.w3.org/2001/XMLSchema" targetNamespace="%s/2009/07/schema"/>
            </types>
        </wsdl:definitions> """ % (globals.plc_ns, globals.plc_ns, globals.plc_ns, globals.plc_ns)
        self.types = xml.dom.minidom.parseString(wsdl_text_header)
        

    def add_wsdl_types(self):
        wsdl_types = self.wsdl.importNode(self.types.getElementsByTagName("types")[0], True)
        self.wsdl.firstChild.appendChild(wsdl_types)

    def generate_wsdl(self):
        self.compute_wsdl_definitions_and_types()
        self.compute_wsdl_definitions()
        self.add_wsdl_ports_and_bindings()
        self.add_wsdl_types()
        self.add_wsdl_services()

    def pretty_print(self):
        if (self.wsdl):
            xml.dom.ext.PrettyPrint(self.wsdl)
        else:
            raise Exception("Empty WSDL")

def main():
    parser = OptionParser()
    parser.add_option("-r", "--registry", dest="registry", action="store_true", 
                              help="Generate registry.wsdl", metavar="FILE")
    parser.add_option("-s", "--slice-manager",
                              action="store_true", dest="slicemgr", 
                              help="Generate sm.wsdl")
    parser.add_option("-a", "--aggregate", action="store_true", dest="aggregate",
                              help="Generate am.wsdl")
    parser.add_option("-c", "--component", action="store_true", dest="component",
                              help="Generate cm.wsdl")
    parser.add_option("-g", "--geni-aggregate", action="store_true", dest="geni_am",
                      help="Generate gm.wsdl")
    parser.add_option("-l", "--lite", action="store_true", dest="lite",
                              help="Generate LITE version of the interface, in which calls exclude credentials")
    (interface_options, args) = parser.parse_args()

    gen = WSDLGen(interface_options)
    gen.generate_wsdl()
    gen.pretty_print()
    

if __name__ == "__main__":
        main()
