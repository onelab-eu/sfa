
class ReturnValue(dict):
    

    @staticmethod
    def get_code(return_value):
        return ReturnValue.get_key_value('code', return_value) 

    @staticmethod
    def get_value(return_value):
        return ReturnValue.get_key_value('value', return_value) 

    @staticmethod
    def get_output(return_value):
        return ReturnValue.get_key_value('output', return_value) 

    @staticmethod
    def get_key_value(key, return_value):
        if isinstance(return_value, dict) and return_value.has_key(key):
            return return_value.get(key)
        else:
            return return_value              
