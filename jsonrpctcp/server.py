"""
This module holds all of the functions and classes necessary for 
initiating a JSONRPC-TCP Server.
"""

import threading
import socket
import time
import sys
import types
import traceback
from jsonrpctcp.handler import Handler
from jsonrpctcp import config
from jsonrpctcp import logger
from jsonrpctcp import history
from jsonrpctcp.errors import ProtocolError
from jsonrpctcp.errors import JSONRPC_ERRORS, EncryptionMissing
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
        if config.secret and not config.crypt:
            raise EncryptionMissing('No encrpytion library found.')
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
        self.socket.listen(config.max_queue)
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
        self.socket = None
        self.client_address = None
        
    def process(self, sock, addr):
        """
        Retrieves the data stream from the socket and validates it.
        """
        self.socket = sock
        self.socket.settimeout(config.timeout)
        self.client_address = addr
        requestlines = []
        while True:
            data = self.get_data()
            if not data: 
                break
            requestlines.append(data)
            if len(data) < config.buffer: 
                break
        request = ''.join(requestlines)
        response = ''
        crypt_error = False
        if config.secret:
            crypt = config.crypt.new(config.secret)
            try:
                request = crypt.decrypt(request)
            except ValueError:
                crypt_error = True
                error = ProtocolError(-32700, 'Could not decrypt request.')
                response = json.dumps(error.generate_error())
        history.request = request
        logger.debug('SERVER | REQUEST: %s' % request)
        if self.socket_error:
            self.socket.close()
        else:
            if not crypt_error:
                response = self.parse_request(request)
            history.response = response
            logger.debug('SERVER | RESPONSE: %s' % response)
            if config.secret:
                length = config.crypt_chunk_size
                pad_length = length - (len(response) % length)
                response = crypt.encrypt('%s%s' % (response, ' '*pad_length))
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
        
    def parse_request(self, data):
        """ Attempts to load the request, validates it, and calls it. """
        try:
            obj = json.loads(data)
        except ValueError:
            return json.dumps(ProtocolError(-32700).generate_error())
        if not obj:
            return json.dumps(ProtocolError(-32600).generate_error())
        batch = True
        if type(obj) is not list:
            batch = False
            obj = [obj,]
        responses = []
        for req in obj:
            request_error = ProtocolError(-32600)
            if type(req) is not dict:
                responses.append(request_error.generate_error())
            elif 'method' not in req.keys() or \
                type(req['method']) not in types.StringTypes:
                responses.append(request_error.generate_error())
            else:
                result = self.parse_call(req)
                if req.has_key('id'):
                    response = generate_response(result, id=req.get('id'))
                    responses.append(response)
        if not responses:
            # It's either a batch of notifications or a single
            # notification, so return nothing.
            return ''
        else:
            if not batch:
                # Single request
                responses = responses[0]
            return json.dumps(responses)
        
    def parse_call(self, obj):
        """
        Parses a JSON request.
        """
            
        # Get ID, Notification if None
        # This is actually incorrect, as IDs can be null by spec (rare)
        request_id = obj.get('id', None)
        
        # Check for required parameters
        jsonrpc = obj.get('jsonrpc', None)
        method = obj.get('method', None)
        if not jsonrpc or not method:
            return ProtocolError(-32600)
        
        # Validate parameters
        params = obj.get('params', [])
        if type(params) not in (list, dict):
            return ProtocolError(-32602)
        
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
                return response
            except Exception:
                logger.error('Error calling handler %s' % method)
                message = traceback.format_exc().splitlines()[-1]
                error_code = -32603
        else:
            error_code = -32601
        return ProtocolError(error_code, message=message)
            
def generate_response(result, **kwargs):
    """
    TODO: Fix so that a request_id can be Null and not a Notification.
    """
    if type(result) is ProtocolError:
        return result.generate_error(**kwargs)
    else:
        response = {'jsonrpc':"2.0", "result":result}
        response.update(kwargs)
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
        
    def summation(*args):
        return sum(args)
        
    if '-v' in sys.argv:
        import logging
        config.verbose = True
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.DEBUG)
        
    server = Server((host, port))
    server.add_handler(echo)
    server.add_handler(echo, 'tree.echo')
    server.add_handler(summation, 'sum')
    server_thread = threading.Thread(target=server.serve)
    server_thread.daemon = True
    server_thread.start()
    
    print "Server running: %s:%s" % (host, port)
    
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print 'Finished.'
        sys.exit()
    
    
if __name__ == "__main__":
    test_server()
