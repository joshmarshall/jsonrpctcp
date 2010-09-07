"""
This is just a list of the Exception classes used, and the
error codes used by them.
"""

JSONRPC_ERRORS = {
    -32700: {'code':-32700, 'message':'Parse error.'},
    -32600: {'code':-32600, 'message':'Invalid request.'},
    -32601: {'code':-32601, 'message':'Method not found.'},
    -32602: {'code':-32602, 'message':'Invalid parameters.'},
    -32603: {'code':-32603, 'message':'Internal error.'},
}

class ProtocolError(Exception):
    """ Used for system errors and custom errors. """
    
    def __init__(self, code, message=None, data=None):
        message = message or \
            JSONRPC_ERRORS.get(code, {}).get('message', 'Unknown error.')
        self.message = message
        self.code = code
        self.data = data
        
    def generate_error(self, *args, **kwargs):        
        response = {
            'jsonrpc':"2.0", 
            'error': {
                'message': self.message,
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