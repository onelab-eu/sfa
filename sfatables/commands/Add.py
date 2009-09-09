import os, time
import libxml2
from sfatables.command import Command
from sfatables.globals import *

class Add(Command):
    options = [('-A','--add')]
    help = 'Add a rule to a chain'
    matches = True
    targets = True

    def __init__(self):
        return

    def getnextfilename(self,type,chain):
        dir = sfatables_config + chain;
        last_rule_number = 1

        for (root, dirs, files) in os.walk(dir):
            for file in files:
                if (file.startswith('sfatables-')):
                    number_str = file.split('-')[1]
                    number = int(number_str)
                    if (number>last_rule_number):
                        last_rule_number = number

        return "sfatables-%d-%s"%(last_rule_number+1,type)

    def call(self, command_options, match_options, target_options):
        filename = match_dir + "/"+match_options.match_name+".xml"
        xmldoc = libxml2.parseFile(filename)
    
        p = xmldoc.xpathNewContext()

        supplied_arguments = match_options.arguments
        for option in supplied_arguments:
            option_name = option['name']
            option_value = getattr(match_options,option_name)

            if (hasattr(match_options,option_name)):
                context = p.xpathEval("//rule/argument[name='%s']"%option_name)
                if (not context):
                    raise Exception('Unknown option %s for match %s'%(option,option['name']))
                else:
                    # Add the value of option
                    valueNode = libxml2.newNode('value')
                    valueNode.addContent(option_value)
                    context[0].addChild(valueNode)

        chain = command_options.args[0]
        filename = self.getnextfilename('match',chain)
        file_path = sfatables_config + '/' + chain + '/' + filename
        xmldoc.saveFile(file_path)
        p.xpathFreeContext()
        xmldoc.freeDoc()

        return True
