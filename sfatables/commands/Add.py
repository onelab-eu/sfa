import os
import libxml2
from sfatables.command import Command
from sfatables.globals import sfatables_config, target_dir, match_dir

class Add(Command):
    def __init__(self):
        self.options = [('-A','--add')]
        self.help = 'Add a rule to a chain'
        self.matches = True
        self.targets = True
        return

    def getnextfilename(self,type,chain):
        dir = sfatables_config + "/"+chain;
        last_rule_number = 0

        for (root, dirs, files) in os.walk(dir):
            for file in files:
                if (file.startswith('sfatables-') and file.endswith(type)):
                    number_str = file.split('-')[1]
                    number = int(number_str)
                    if (number>last_rule_number):
                        last_rule_number = number

        return "sfatables-%d-%s"%(last_rule_number+1,type)

    def call_gen(self, chain, type, dir, options):
        filename = os.path.join(dir, options.name+".xml")
        xmldoc = libxml2.parseFile(filename)
    
        p = xmldoc.xpathNewContext()

        supplied_arguments = options.arguments
        if (hasattr(options,'element') and options.element):
            element = options.element
        else:
            element='*'

        for option in supplied_arguments:
            option_name = option['name']
            option_value = getattr(options,option_name)

            if (hasattr(options,option_name) and getattr(options,option_name)):
                context = p.xpathEval("//rule[@element='%s' or @element='*']/argument[name='%s']"%(element, option_name))
                if (not context):
                    raise Exception('Unknown option %s for match %s and element %s'%(option,option['name'], element))
                else:
                    # Add the value of option
                    valueNode = libxml2.newNode('value')
                    valueNode.addContent(option_value)
                    context[0].addChild(valueNode)

        filename = self.getnextfilename(type,chain)
        file_path = os.path.join(sfatables_config, chain, filename)
        if not os.path.isdir(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        xmldoc.saveFile(file_path)
        p.xpathFreeContext()
        xmldoc.freeDoc()

        return True

    def call(self, command_options, match_options, target_options):
        chain = command_options.args[0]
        ret = self.call_gen(chain, 'match',match_dir, match_options)
        if (ret):
            ret = self.call_gen(chain, 'target',target_dir, target_options)

        return ret
