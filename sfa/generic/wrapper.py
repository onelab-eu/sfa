class Wrapper:

    def match_dict(self, dic, filter):
       # We suppose if a field is in filter, it is therefore in the dic
       if not filter:
           return True
       match = True
       for k, v in filter.items():
           if k[0] in Filter.modifiers:
               op = k[0]
               k = k[1:]
           elif k in ['-SORT', '-LIMIT', '-OFFSET']:
               continue;
           else:
               op = '='

           if op == '=':
               if isinstance(v, list):
                   match &= (dic[k] in v) # array ?
               else:
                   match &= (dic[k] == v)
           elif op == '~':
               if isinstance(v, list):
                   match &= (dic[k] not in v) # array ?
               else:
                   match &= (dic[k] != v) # array ?
           elif op == '<':
               if isinstance(v, StringTypes):
                   # prefix match
                   match &= dic[k].startswith('%s.' % v)
               else:
                   match &= (dic[k] < v)
           elif op == '[':
               if isinstance(v, StringTypes):
                   match &= dic[k] == v or dic[k].startswith('%s.' % v)
               else:
                   match &= (dic[k] <= v)
           elif op == '>':
               if isinstance(v, StringTypes):
                   # prefix match
                   match &= v.startswith('%s.' % dic[k])
               else:
                   match &= (dic[k] > v)
           elif op == ']':
               if isinstance(v, StringTypes):
                   # prefix match
                   match &= dic[k] == v or v.startswith('%s.' % dic[k])
               else:
                   match &= (dic[k] >= v)
           elif op == '&':
               match &= (dic[k] & v) # array ?
           elif op == '|':
               match &= (dic[k] | v) # array ?
           elif op == '{':
               match &= (v in dic[k])
       return match

    def project_select_and_rename_fields(self, table, pkey, filters, fields):
        filtered = []
        for row in table:
            # apply input filters 
            if self.selection or self.match_dict(row, filters):
                # apply output_fields
                if self.projection:
                    filtered.append(row)
                else:
                    c = {}
                    for k,v in row.items():
                        # if no fields = keep everything
                        if not fields or k in fields or k == pkey:
                            c[k] = v
                    filtered.append(c)
        return filtered

    def get_objects(self, method, filters=None, fields=None):
        if not method in ['authorities', 'resources', 'users', 'slices']:
            raise Exception, "Unknown object type"
        results = self.get(method, filters, fields)
        # Perform missing operations
        if results and (filter and not self.selection) or (fields and not self.projection):
            results = self.project_select_and_rename_fields(results, 'id', filters, fields)
        return results
