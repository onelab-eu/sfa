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
        if input in self.names: return input
        matches=[ name for name in self.names if Candidates.fits(input,name) ]
        if len(matches)==1: return matches[0]
        else: return None

#################### minimal test
candidates_specs=[
('create delete reset resources slices start status stop version create_gid', 
  [ ('ver','version'),
    ('r',None),
    ('re',None),
    ('res',None),
    ('rese','reset'),
    ('reset','reset'),
    ('reso','resources'),
    ('sli','slices'),
    ('st',None),
    ('sta',None),
    ('stop','stop'),
    ('a',None),
    ('cre',None),
    ('create','create'),
    ('create_','create_gid'),
    ('create_g','create_gid'),
    ('create_gi','create_gid'),
    ('create_gid','create_gid'),
])
]

def test_candidates ():
    for (names, tuples) in candidates_specs:
        names=names.split()
        for (input,expected) in tuples:
            got=Candidates(names).only_match(input)
            if got==expected: print '.',
            else: print 'X FAIL','names[',names,'] input',input,'expected',expected,'got',got

if __name__ == '__main__':
    test_candidates()
