import os, time
import libxml2
from sfatables.command import Command
from sfatables.globals import sfatables_config, target_dir, match_dir

class Insert(Command):
    def __init__(self):
        self.options = [('-I','--insert')]
        self.help = 'Insert a rule into a chain'
        self.matches = True
        self.targets = True
        return

    def call_gen(self, chain, type, dir, options, file_path):
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

        if not os.path.isdir(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        xmldoc.saveFile(file_path)
        p.xpathFreeContext()
        xmldoc.freeDoc()

        return True

    def call(self, command_options, match_options, target_options):
        if (len(command_options.args)<2):
            print "Please specify the chain and the rule number to insert, e.g. sfatables -I INCOMING 1 -- ...."
            return

        chain = command_options.args[0]

        rule_number = command_options.args[1]
        chain_dir = sfatables_config + "/" + chain

        match_path = chain_dir + "/" + "sfatables-%s-match"%rule_number
        target_path = chain_dir + "/" + "sfatables-%s-target"%rule_number

        ret = self.call_gen(chain, 'match',match_dir, match_options, match_path)
        if (ret):
            ret = self.call_gen(chain, 'target',target_dir, target_options, target_path)

        return ret
