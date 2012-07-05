### utility to match command-line args to names
class Candidates:
    def __init__ (self, names):
        self.names=names
    # is an input string acceptable for one of the known names?
    @staticmethod
    def fits (input, name):
        return name.find(input)==0
    # returns one of the names if the input name has a unique match
    # or None otherwise
    def only_match (self, input):
        matches=[ name for name in self.names if Candidates.fits(input,name) ]
        if len(matches)==1: return matches[0]
        else: return None

