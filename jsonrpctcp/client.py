import socket 
import json
import uuid
from config import config

class Client(object):

    _requests = None
    _request = None
    _response = None

    def __init__(self, addr, batch=False):
        self._addr = addr
        self._requests = []
        self.__batch = batch
        
    def __getattr__(self, key):
        if key.startswith('_'):
            print key
            raise AttributeError('Methods that start with _ are not allowed.')
        req_id = u'%s' % uuid.uuid4()
        request = ClientRequest(self, namespace=key, req_id=req_id)
        self._requests.append(request)
        return request
        
    @property
    def _notify(self):
        request = ClientRequest(
            self,
            notify = True,
            req_id = None
        )
        self._requests.append(request)
        return request
        
    def _batch(self):
        return Client(self._addr, batch=True)
        
    def _is_batch(self):
        return self.__batch is True
        
    def __call__(self):
        assert len(self._requests) > 0
        requests = []
        for req in self._requests:
            requests.append(req._request)
        if not self._is_batch():
            result = self._call_single(requests[0])
        else:
            result = self._call_batch(requests)
        self._requests = []
        return result
            
    def _call_single(self, request):
        self._request = request
        response = self._send_and_receive(request)
        if not response:
            return response
        self._response = response        
        self._validate_response(response)
        return response['result']
        
    def _call_batch(self, requests):
        ids = []
        for request in requests:
            if request.has_key('id'):
                ids.append(request['id'])
        self._request = requests
        responses = self._send_and_receive(requests)
        self._responses = responses
        assert type(responses) is list
        response_by_id = {}
        for response in responses:
            response_by_id[response.get('id', None)] = response
        for request_id in ids:
            response = response_by_id.get(request_id)
            self._validate_response(response)
            yield response['result']
    
    def _send_and_receive(self, request):
        message = json.dumps(request)
        if config.verbose:
            print 'REQUEST:', request
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(config.timeout)
        sock.connect(self._addr)
        sock.send(message)
        if type(request) is dict and not request.has_key('id'):
            # single notification, we don't need a response.
            sock.close()
            return None
        response = ''
        while True:
            try:
                data = sock.recv(config.buffer)
            except socket.timeout:
                break
            if not data: break
            response += data
            if len(response) < config.buffer:
                break
        sock.close()
        if config.verbose:
            print 'RESPONSE:', response
        obj = json.loads(response)
        return obj
        
    def _validate_response(self, response):
        jsonrpc = response.has_key('jsonrpc')
        response_id = response.has_key('id')
        result = response.has_key('result')
        error = response.has_key('error')
        if not jsonrpc or not response_id or not result:
            raise Exception('Server returned invalid results.')
        if error:
            raise Exception('ERROR %d: %s' % (
                response['error']['code'], 
                response['error']['message']
            ))
           
class ClientRequest(object):

    def __init__(self, client, namespace='', notify=False, req_id=None):
        self._client = client
        self._namespace = namespace
        self._notify = notify
        self._req_id = req_id
        self._request = None

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError
        if self._namespace:
            self._namespace += '.'
        self._namespace += key
        return self
    
    def __call__(self,  *args, **kwargs):
        if not (len(args) == 0 or len(kwargs) == 0):
            raise ValueError(
                "JSON spec allows positional arguments OR " + \
                "keyword arguments, not both."
            )
        params = list(args)
        if len(kwargs) > 0:
            params = kwargs
        return self._call_server(params)
        
    def _call_server(self, params):
        request = {
            'jsonrpc':'2.0', 
            'method': self._namespace
        }
        if params:
            request['params'] = params
        if not self._notify:
            request['id'] = self._req_id
        self._request = request
        if not self._client._is_batch():
            return self._client()
        # Add batch logic here
        
def connect(host, port):
    client = Client((host, port))
    return client
    
if __name__ == "__main__":
    import sys    
    if '-v' in sys.argv:
        config.verbose = True
    conn = connect('localhost', 8080)
    value = 'Testing!'
    result = conn.echo(value)
    assert result == value
    print 'Single test completed.'
    
    result = conn._notify.echo(message='No response!')
    assert result == None
    print 'Notify test completed.'
    
    batch = conn._batch()
    batch.tree.echo(message="First!")
    batch._notify.echo("Skip!")
    batch.tree.echo("Last!")
    results = []
    for i in batch():
        results.append(i)
    assert results == ['First!', 'Last!']
    print 'Batch test completed.'
    
    result = conn.echo(message=5)
    assert result == 5
    print 'Post-batch test completed.'
    
    try:
        conn.echo()
    except Exception:
        print 'Bad call had necessary exception.'
    else:
        print 'ERROR: Did not throw exception for bad call.'
    
    print '============================='
    print "Tests completed successfully."
