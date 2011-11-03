import os, time
from sfatables.globals import sfatables_config
from sfatables.command import Command

class Delete(Command):
    options = [('-D','--delete')]
    help = 'Delete a rule from a chain'
    key='delete_rule'
    matches = False
    targets = False

    def __init__(self):
        return

    def call(self, command_options, match_options, target_options):

        if (len(command_options.args)<2):
            print "Please specify the chain and the rule number to delete, e.g. sfatables -D INCOMING 1."
            return

        chain = command_options.args[0]


        rule_number = command_options.args[1]
        chain_dir = sfatables_config + "/" + chain

        match_path = chain_dir + "/" + "sfatables-%s-match"%rule_number
        target_path = chain_dir + "/" + "sfatables-%s-target"%rule_number

        os.unlink(match_path)
        os.unlink(target_path)

