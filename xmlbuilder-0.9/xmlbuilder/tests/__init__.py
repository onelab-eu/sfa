#!/usr/bin/env python
from __future__ import with_statement
#-------------------------------------------------------------------------------
import unittest
from xml.etree.ElementTree import fromstring
#-------------------------------------------------------------------------------
from xmlbuilder import XMLBuilder
#-------------------------------------------------------------------------------
def xmlStructureEqual(xml1,xml2):
    tree1 = fromstring(xml1)
    tree2 = fromstring(xml2)
    return _xmlStructureEqual(tree1,tree2)
#-------------------------------------------------------------------------------
def _xmlStructureEqual(tree1,tree2):
    if tree1.tag != tree2.tag:
        return False
    attr1 = list(tree1.attrib.items())
    attr1.sort()
    attr2 = list(tree2.attrib.items())
    attr2.sort()
    if attr1 != attr2:
        return False
    return tree1.getchildren() == tree2.getchildren()
#-------------------------------------------------------------------------------
result1 = \
"""
<root>
    <array />
    <array len="10">
        <el val="0" />
        <el val="1">xyz</el>
        <el val="2">abc</el>
        <el val="3" />
        <el val="4" />
        <el val="5" />
        <sup-el val="23">test  </sup-el>
    </array>
</root>
""".strip()
#-------------------------------------------------------------------------------
class TestXMLBuilder(unittest.TestCase):
    def testShift(self):
        xml = (XMLBuilder() << ('root',))
        self.assertEqual(str(xml),"<root />")
        
        xml = XMLBuilder()
        xml << ('root',"some text")
        self.assertEqual(str(xml),"<root>some text</root>")
        
        xml = XMLBuilder()
        xml << ('root',{'x':1,'y':'2'})
        self.assert_(xmlStructureEqual(str(xml),"<root x='1' y='2'>some text</root>"))
        
        xml = XMLBuilder()
        xml << ('root',{'x':1,'y':'2'})
        self.assert_(xmlStructureEqual(str(xml),"<root x='1' y='2'></root>"))

        xml = XMLBuilder()
        xml << ('root',{'x':1,'y':'2'})
        self.assert_(not xmlStructureEqual(str(xml),"<root x='2' y='2'></root>"))

        
        xml = XMLBuilder()
        xml << ('root',"gonduras.ua",{'x':1,'y':'2'})
        self.assert_(xmlStructureEqual(str(xml),"<root x='1' y='2'>gonduras.ua</root>"))
        
        xml = XMLBuilder()
        xml << ('root',"gonduras.ua",{'x':1,'y':'2'})
        self.assert_(xmlStructureEqual(str(xml),"<root x='1' y='2'>gonduras.com</root>"))
    #---------------------------------------------------------------------------
    def testWith(self):
        xml = XMLBuilder()
        with xml.root(lenght = 12):
            pass
        self.assertEqual(str(xml),'<root lenght="12" />')
        
        xml = XMLBuilder()
        with xml.root():
            xml << "text1" << "text2" << ('some_node',)
        self.assertEqual(str(xml),"<root>text1text2<some_node /></root>")
    #---------------------------------------------------------------------------
    def testFormat(self):
        x = XMLBuilder('utf-8',format = True)
        with x.root():
            x << ('array',)
            with x.array(len = 10):
                with x.el(val = 0):
                    pass
                with x.el('xyz',val = 1):
                    pass
                x << ("el","abc",{'val':2}) << ('el',dict(val=3))
                x << ('el',dict(val=4)) << ('el',dict(val='5'))
                with x('sup-el',val = 23):
                    x << "test  "
        self.assertEqual(str(x),result1)
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    unittest.main()
#-------------------------------------------------------------------------------
