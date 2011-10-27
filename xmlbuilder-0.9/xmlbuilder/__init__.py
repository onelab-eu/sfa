#!/usr/bin/env python
#-------------------------------------------------------------------------------
from __future__ import with_statement
#-------------------------------------------------------------------------------
from xml.etree.ElementTree import TreeBuilder,tostring
#-------------------------------------------------------------------------------
__all__ = ["XMLBuilder"]
__doc__ = """
XMLBuilder is simple library build on top of ElementTree.TreeBuilder to
simplify xml files creation as much as possible. Althow it can produce
structured result with identated child tags. `XMLBuilder` use python `with`
statement to define xml tag levels and `<<` operator for simple cases -
text and tag without childs.

from __future__ import with_statement
from xmlbuilder import XMLBuilder
x = XMLBuilder(format=True)
with x.root(a = 1):
    with x.data:
        [x << ('node',{'val':i}) for i in range(10)]

etree_node = ~x
print str(x)
"""
#-------------------------------------------------------------------------------
class _XMLNode(object):
    """Class for internal usage"""
    def __init__(self,parent,name,builder):
        self.builder = builder
        self.name = name
        self.text = []
        self.attrs = {}
        self.entered = False
        self.parent = parent
    def __call__(self,*dt,**mp):
        text = "".join(dt)
        if self.entered:
            self.builder.data(text)
        else:
            self.text.append(text)
        if self.entered:
            raise ValueError("Can't add attributes to already opened element")
        smp = dict((k,str(v)) for k,v in mp.items())
        self.attrs.update(smp)
        return self
    def __enter__(self):
        self.parent += 1
        self.builder.start(self.name,self.attrs)
        self.builder.data("".join(self.text))
        self.entered = True
        return self
    def __exit__(self,x,y,z):
        self.parent -= 1
        self.builder.end(self.name)
        return False
#-------------------------------------------------------------------------------
class XMLBuilder(object):
    """XmlBuilder(encoding = 'utf-8', # result xml file encoding
            builder = None, #etree.TreeBuilder or compatible class
            tab_level = None, #current tabulation level - string
            format = False,   # make formatted output
            tab_step = " " * 4) # tabulation step
    use str(builder) or unicode(builder) to get xml text or
    ~builder to obtaine etree.ElementTree
    """
    def __init__(self,encoding = 'utf-8',
                      builder = None,
                      tab_level = None,
                      format = False,
                      tab_step = " " * 4):
        self.__builder = builder or TreeBuilder()
        self.__encoding = encoding 
        if format :
            if tab_level is None:
                tab_level = ""
        if tab_level is not None:
            if not format:
                raise ValueError("format is False, but tab_level not None")
        self.__tab_level = tab_level # current format level
        self.__tab_step = tab_step   # format step
        self.__has_sub_tag = False   # True, if current tag had childrens
        self.__node = None
    # called from _XMLNode when tag opened
    def __iadd__(self,val):
        self.__has_sub_tag = False
        if self.__tab_level is not None:
            self.__builder.data("\n" + self.__tab_level)
            self.__tab_level += self.__tab_step
        return self
    # called from XMLNode when tag closed
    def __isub__(self,val):
        if self.__tab_level is not None:
            self.__tab_level = self.__tab_level[:-len(self.__tab_step)]
            if self.__has_sub_tag:
                self.__builder.data("\n" + self.__tab_level)
        self.__has_sub_tag = True
        return self
    def __getattr__(self,name):
        return _XMLNode(self,name,self.__builder)
    def __call__(self,name,*dt,**mp):
        x = _XMLNode(self,name,self.__builder)
        x(*dt,**mp)
        return x
    #create new tag or add text
    #possible shift values
    #string - text
    #tuple(string1,string2,dict) - new tag with name string1,attrs = dict,and text string2
    #dict and string2 are optional
    def __lshift__(self,val):
        if isinstance(val,basestring):
            self.__builder.data(val)
        else:
            self.__has_sub_tag = True
            assert hasattr(val,'__len__'),\
                'Shifted value should be tuple or list like object not %r' % val
            assert hasattr(val,'__getitem__'),\
                'Shifted value should be tuple or list like object not %r' % val
            name = val[0]
            if len(val) == 3:
                text = val[1]
                attrs = val[2]
            elif len(val) == 1:
                text = ""
                attrs = {}
            elif len(val) == 2:
                if isinstance(val[1],basestring):
                    text = val[1]
                    attrs = {}
                else:
                    text = ""
                    attrs = val[1]
            if self.__tab_level is not None:
                self.__builder.data("\n" + self.__tab_level)
            self.__builder.start(name,
                                 dict((k,str(v)) for k,v in attrs.items()))
            if text:
                self.__builder.data(text)
            self.__builder.end(name)
        return self # to allow xml << some1 << some2 << some3
    #close builder
    def __invert__(self):
        if self.__node is not None:
            return self.__node
        self.__node = self.__builder.close()
        return self.__node
    def __str__(self):
        """return generated xml"""
        return tostring(~self,self.__encoding)
    def __unicode__(self):
        """return generated xml"""
        res = tostring(~self,self.__encoding)
        return res.decode(self.__encoding)
#-------------------------------------------------------------------------------
