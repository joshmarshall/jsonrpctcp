import threading
import socket
import time
import sys
import traceback
import collections
from handler import Handler
from inspect import isclass
from config import config

try:
    import json
except:
    import simplejson as json

class Server(object):

    _shutdown = False

    def __init__(self, addr, handler=None, pool=10):
        self.addr = addr
        self.threads = []
        # Pool not actually implemented yet
        self.pool = pool
        self.json_request = JSONRequest(self)
        if handler:
            assert issubclass(handler, collection.Callable) or \
                issubclass(handler, Handler)
            self.json_request.add_handler(handler)
        
    def serve(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.addr)
        self.socket.listen(3)
        self.wait()
        
    def wait(self):
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
        for t in self.threads:
            t.join()
        sys.stdout.write('done.\n')

    def shutdown(self):
        self._shutdown = True
        self.socket.close()
        
    def check_threads(self):
        for t in self.threads:
            if not t.is_alive():
                t.join()
                self.threads.remove(t)
    
    def add_handler(self, method, name=None):
        # Just a wrapper around JSONRequest.add_handler
        self.json_request.add_handler(method, name)
            
class JSONRequest(object):

    def __init__(self, server):
        self.server = server
        self.handlers = {}

    def add_handler(self, method, name=None):
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
            assert isinstance(method, collections.Callable)
            self.handlers[name] = method
            
    def get_handler(self, name):
        if self.handlers.has_key(name):
            return self.handlers[name]
        return None
                
    def process(self, sock, addr):
        request = ProcessRequest(self)
        request.process(sock, addr)
        
class ProcessRequest(object):

    socket_error = False

    def __init__(self, json_request):
        self.json_request = json_request
        
    def process(self, sock, addr):
        self.socket = sock
        self.socket.settimeout(config.timeout)
        self.client_address = addr
        self.data = ''
        while True:
            data = self.get_data()
            if not data: break
            self.data += data
            if len(data) < config.buffer: break
        if config.verbose:
            print 'REQUEST:', self.data
        if self.socket_error:
            self.socket.close()
        else:
            response = self.parse_request()
            if response:
                if config.verbose:
                    print 'RESPONSE:', response
                self.socket.send(response) 
        self.socket.close()

    def get_data(self):
        try:
            data = self.socket.recv(config.buffer)
        except socket.timeout:
            """
            It may have finished sending without an error if
            len(message) % buffer == 0.
            """
            data = None
        except socket.error:
            self.socket_error = True
            data = None
        return data
        
    def parse_request(self):
        try:
            obj = json.loads(self.data)
        except ValueError:
            return self.error(-32700)
        
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
            return self.error(-32600, force=True)
            
        # Get ID, Notification if None
        # This is actually incorrect, as IDs can be null by spec (rare)
        request_id = obj.get('id', None)
        
        # Check for required parameters
        jsonrpc = obj.get('jsonrpc', None)
        method = obj.get('method', None)
        if not jsonrpc or not method:
            return self.error(-32600, request_id)
        
        # Validate parameters
        params = obj.get('params', [])
        if type(params) not in (list, dict):
            return self.error(-32602, request_id)
        
        # Parse Request
        kwargs = {}
        if type(params) is dict:
            kwargs = params
            params = []
        handler = self.json_request.get_handler(method)
        if handler:
            try:
                response = handler(*params, **kwargs)
                return self.response(response, request_id)
            except:
                traceback.print_exc()
                return self.error(-32603, request_id)
        return self.error(-32601, request_id)
            
    def response(self, value, request_id):
        """
        TODO: Fix so that a request_id can be Null and not a Notification.
        """
        if not request_id:
            return None
        response = {'jsonrpc':"2.0", 'result':value, 'id':request_id}
        return response
        
    def error(self, code, request_id=None, force=True):
        """
        TODO: Fix so that a request_id can be Null and not a Notification.
        """
        if not request_id and not force:
            return None
        response = {'jsonrpc':"2.0", 'error':errors.get(code), 'id':request_id}
        return response
        
        
def start_server(ip, port, handler):
    
    server = Server((ip, port))
    server.add_handler(handler)
    server_thread = threading.Thread(target=server.serve)
    server_thread.daemon = True
    server_thread.start()
    return server
    
    
    
errors = {
    -32700: {'code':-32700, 'message':'Parse error.'},
    -32600: {'code':-32600, 'message':'Invalid request.'},
    -32601: {'code':-32601, 'message':'Method not found.'},
    -32602: {'code':-32602, 'message':'Invalid parameters.'},
    -32603: {'code':-32603, 'message':'Internal error.'},
}
    
    
if __name__ == "__main__":
    import sys
    HOST, PORT = '', 8080
    
    def echo(message):
        """
        Test method, an example of how simple it *should* be.
        """
        return message
        
    if '-v' in sys.argv:
        config.verbose = True
        
    server = Server((HOST, PORT))
    server.add_handler(echo)
    server.add_handler(echo, 'tree.echo')
    server_thread = threading.Thread(target=server.serve)
    server_thread.daemon = True
    server_thread.start()
    
    print "Server running: %s:%s" % (HOST, PORT)
    
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        server.shutdown()
        
    print 'Finished.'
