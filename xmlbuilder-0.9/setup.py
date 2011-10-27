#!/usr/bin/env python
#-------------------------------------------------------------------------------
import os
import sys
import glob
import os.path
from setuptools import setup
#from distutils.core import setup
#-------------------------------------------------------------------------------
if 'upload' in sys.argv:
    # for .pypirc file
    try:
        os.environ['HOME']
    except KeyError:
        os.environ['HOME'] = '..\\'
#-------------------------------------------------------------------------------
fpath = lambda x : os.path.join(*x.split('/'))
#-------------------------------------------------------------------------------
PYPI_URL = 'http://pypi.python.org/pypi/xmlbuilder'
ld = open(fpath('xmlbuilder/docs/long_descr.rst')).read()
ld = ld.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
setup(
    name = "xmlbuilder",
    fullname = "xmlbuilder",
    version = "0.9",
    packages = ["xmlbuilder"],
    package_dir = {'xmlbuilder':'xmlbuilder'},
    author = "koder",
    author_email = "koder_dot_mail@gmail_dot_com",
    maintainer = 'koder',
    maintainer_email = "koder_dot_mail@gmail_dot_com",
    description = "Pythonic way to create xml files",
    license = "MIT",
    keywords = "xml",
    test_suite = "xml_buider.tests",
    url = PYPI_URL,
    download_url = PYPI_URL,
    long_description = ld,
    #include_package_data = True,
    #package_data = {'xmlbuilder':["docs/*.rst"]},
    #data_files = [('', ['xmlbuilder/docs/long_descr.rst'])]
)
#-------------------------------------------------------------------------------
