"""
This module holds all of the functions and classes necessary for 
initiating a JSONRPC-TCP Server.
"""

import threading
import socket
import time
import sys
import traceback
from jsonrpctcp.handler import Handler
from jsonrpctcp.config import config
from jsonrpctcp.logger import logger
from inspect import isclass

try:
    import json
except ImportError:
    import simplejson as json

class Server(object):
    """
    This class is the basic Server object. It should be instantiated
    with a (host, port) tuple (and an optional handler), and then
    the Handler subclasses / functions should be attached through the
    add_handler method.
    """

    _shutdown = False

    def __init__(self, addr, handler=None, pool=10):
        self.addr = addr
        self.socket = None
        self.threads = []
        # Pool not actually implemented yet
        self.pool = pool
        self.json_request = JSONRequest(self)
        if handler:
            assert hasattr(handler, '__call__') or \
                issubclass(handler, Handler)
            self.json_request.add_handler(handler)
        
    def serve(self):
        """
        This starts the server -- it blocks, so if there are other
        tasks that need to be performed after the server is started,
        threading / multiprocessing will need to be employed.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.addr)
        self.socket.listen(3)
        self.wait()
        
    def wait(self):
        """ The principle wait cycle. """
        while True:
            if self._shutdown:
                break            
            clientsock, addr = self.socket.accept()
            args = (clientsock, addr)
            target = self.json_request.process
            thread = threading.Thread(target=target, args=args)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)
            self.check_threads()
            
        sys.stdout.write('Shutting down...')
        for thread in self.threads:
            thread.join()
        sys.stdout.write('done.\n')

    def shutdown(self):
        """
        Attempts to shutdown the server.
        TODO: Make this work quickly and properly.
        """
        self._shutdown = True
        self.socket.close()
        
    def check_threads(self):
        """
        Check the thread list for dead threads and finished
        threads.
        """
        for thread in self.threads:
            if not thread.isAlive():
                thread.join()
                self.threads.remove(thread)
    
    def add_handler(self, method, name=None):
        """ Just a wrapper around JSONRequest.add_handler """
        self.json_request.add_handler(method, name)
            
class JSONRequest(object):
    """
    This is the class that handles individual requests passed
    from the server wait cycle.
    """

    def __init__(self, server):
        self.server = server
        self.handlers = {}

    def add_handler(self, method, name=None):
        """
        Attach a handler to the request object. It must be either
        callable, or a subclass of Handler.
        """
        if isclass(method):
            assert issubclass(method, Handler)
            # If it's an actual Handler subclass
            handler_instance = method(self)
            for hname, method in handler_instance._handlers.iteritems():
                if name:
                    hname = '%s.%s' % (name, hname)
                self.handlers[hname] = method
        else:
            if not name:
                name = method.__name__
            assert hasattr(method, '__call__')
            self.handlers[name] = method
            
    def get_handler(self, name):
        """ Check for an attached handler and return it. """
        if self.handlers.has_key(name):
            return self.handlers[name]
        return None
                
    def process(self, sock, addr):
        """ Just a wrapper for ProcessRequest. """
        request = ProcessRequest(self)
        request.process(sock, addr)
        
class ProcessRequest(object):
    """
    This is the class that handles an actual request, passing it through
    the Handler and parsing the response.
    """

    socket_error = False

    def __init__(self, json_request):
        self.json_request = json_request
        self.data = ''
        self.socket = None
        self.client_address = None
        
    def process(self, sock, addr):
        """
        Retrieves the data stream from the socket and validates it.
        """
        self.socket = sock
        self.socket.settimeout(config.timeout)
        self.client_address = addr
        while True:
            data = self.get_data()
            if not data: 
                break
            self.data += data
            if len(data) < config.buffer: 
                break
        logger.debug('REQUEST: %s' % self.data)
        if self.socket_error:
            self.socket.close()
        else:
            response = self.parse_request()
            if response:
                logger.debug('RESPONSE: %s' % response)
                self.socket.send(response) 
        self.socket.close()

    def get_data(self):
        """ Retrieves a data chunk from the socket. """
        try:
            data = self.socket.recv(config.buffer)
        except socket.timeout:
            # It may have finished sending without an error if
            # len(message) % buffer == 0.
            data = None
        except socket.error:
            self.socket_error = True
            data = None
        return data
        
    def parse_request(self):
        """ Attempts to load the request, validates it, and calls it. """
        try:
            obj = json.loads(self.data)
        except ValueError:
            return generate_error(-32700)
        
        # If it's a batch request...
        if type(obj) is list:
            responses = []
            for req in obj:
                response = self.parse_call(req)
                if response:
                    # Ignoring notifications
                    responses.append(response)
            return json.dumps(responses)
        # If it's a single request...
        return json.dumps(self.parse_call(obj))
        
    def parse_call(self, obj):
        """
        Parses a JSON request.
        """
        if type(obj) is not dict:
            return generate_error(-32600, force=True)
            
        # Get ID, Notification if None
        # This is actually incorrect, as IDs can be null by spec (rare)
        request_id = obj.get('id', None)
        
        # Check for required parameters
        jsonrpc = obj.get('jsonrpc', None)
        method = obj.get('method', None)
        if not jsonrpc or not method:
            return generate_error(-32600, request_id)
        
        # Validate parameters
        params = obj.get('params', [])
        if type(params) not in (list, dict):
            return generate_error(-32602, request_id)
        
        # Parse Request
        kwargs = {}
        if type(params) is dict:
            kwargs = params
            params = []
        handler = self.json_request.get_handler(method)
        error_code = None
        message = None
        if handler:
            try:
                response = handler(*params, **kwargs)
                return generate_response(response, request_id)
            except TypeError:
                logger.warning('TypeError when calling handler %s' % method)
                message = traceback.format_exc().splitlines()[-1]
                error_code = -32603
            except Exception:
                logger.error('Error calling handler %s' % method)
                message = traceback.format_exc()
                error_code = -32603
        else:
            error_code = -32601
        return generate_error(error_code, request_id, message=message)
            
def generate_response(value, request_id):
    """
    TODO: Fix so that a request_id can be Null and not a Notification.
    """
    if not request_id:
        return None
    response = {'jsonrpc':"2.0", 'result':value, 'id':request_id}
    return response
    
def generate_error(code, request_id=None, force=True, message=None):
    """
    TODO: Fix so that a request_id can be Null and not a Notification.
    """
    if not request_id and not force:
        return None
    response = {
        'jsonrpc':"2.0", 
        'error': {
            'message': message or JSONRPC_ERRORS.get(code),
            'code': code
        },
        'id':request_id
    }
    return response
    
        
def start_server(host, port, handler):
    """
    Wrapper around Server that pre-threads it.
    """
    server = Server((host, port))
    server.add_handler(handler)
    server_thread = threading.Thread(target=server.serve)
    server_thread.daemon = True
    server_thread.start()
    return server
    
    
    
JSONRPC_ERRORS = {
    -32700: {'code':-32700, 'message':'Parse error.'},
    -32600: {'code':-32600, 'message':'Invalid request.'},
    -32601: {'code':-32601, 'message':'Method not found.'},
    -32602: {'code':-32602, 'message':'Invalid parameters.'},
    -32603: {'code':-32603, 'message':'Internal error.'},
}
    
def test_server():
    """
    Creates a simple server to be tested against the test_client in
    the client module.
    """
    
    host, port = '', 8080
    
    def echo(message):
        """
        Test method, an example of how simple it *should* be.
        """
        return message
        
    if '-v' in sys.argv:
        import logging
        config.verbose = True
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.DEBUG)
        
    server = Server((host, port))
    server.add_handler(echo)
    server.add_handler(echo, 'tree.echo')
    server_thread = threading.Thread(target=server.serve)
    server_thread.daemon = True
    server_thread.start()
    
    print "Server running: %s:%s" % (host, port)
    
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print 'Finished.'
        sys.exit()
    
    
if __name__ == "__main__":
    test_server()
