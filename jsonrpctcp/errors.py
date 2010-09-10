"""
This is just a list of the Exception classes used, and the
error codes used by them.
"""
from jsonrpctcp import config
import random
import string

JSONRPC_ERRORS = {
    -32700: {'code':-32700, 'message':'Parse error.'},
    -32600: {'code':-32600, 'message':'Invalid request.'},
    -32601: {'code':-32601, 'message':'Method not found.'},
    -32602: {'code':-32602, 'message':'Invalid parameters.'},
    -32603: {'code':-32603, 'message':'Internal error.'},
}

# The random characters are used for padding the server error messages 
# so that it will hopefully be  harder to brute-force a secret key.
RANDOM_CHARACTERS = string.letters + string.digits
RANDOM_STRING_LENGTH = 12

class ProtocolError(Exception):
    """ Used for system errors and custom errors. """
    
    def __init__(self, code, message=None, data=None):
        message = message or \
            JSONRPC_ERRORS.get(code, {}).get('message', 'Unknown error.')
        self.message = message
        self.code = code
        self.data = data
        
    def generate_error(self, *args, **kwargs):
        """ 
        Return a proper JSON-RPC structure for error messages.
        This also pads a random string on the message to help
        counter brute-forcing "known" messages.
        """
        message = self.message
        if config.secret:
            random_string = ''.join([
                random.choice(RANDOM_CHARACTERS)
                for i in range(RANDOM_STRING_LENGTH)
            ])
            message = '%s (random: %s)' % (self.message, random_string)        
        response = {
            'jsonrpc':"2.0", 
            'error': {
                'message': message,
                'code': self.code
            },
            'id':kwargs.get('id', None)
        }
        return response
        
    def __repr__(self):
        return (
            '<ProtocolError> code:%s, message:%s, data:%s' %
            (self.code, self.message, self.data)
        )

class EncryptionMissing(Exception):
    """ Simple exception if a crypt library is missing """
    pass