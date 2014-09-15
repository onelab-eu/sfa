#!/usr/bin/env python

from __future__ import print_function

from argparse import ArgumentParser

# sudo pip install markdown
import markdown 
import zipfile

usage="transform README.md into index.html and zip into index.zip"
parser = ArgumentParser(usage=usage)
args = parser.parse_args()

input="README.md"
output="index.html"
zipped="index.zip"

with open(output,"w") as o:
    with open(input) as i:
        html = markdown.markdown (i.read())
        o.write(html)
print ("(Over)written {}".format(output))

with zipfile.ZipFile(zipped,'w') as z:
    z.write(output)
print ("(Over)written {}".format(zipped))

