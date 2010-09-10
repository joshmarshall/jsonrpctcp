"""
These are mostly tests taken verbatim from the JSON RPC v2 Spec document:
http://groups.google.com/group/json-rpc/web/json-rpc-2-0

JSON-RPC v1 tests will be coming soon, as will tests for library "features"
like class translation, etc.

"""
from jsonrpctcp import connect, config, history
from jsonrpctcp.server import Server
from jsonrpctcp import logger
from jsonrpctcp.errors import ProtocolError, EncryptionMissing
import unittest
import os
import time
try:
    import json
except ImportError:
    import simplejson as json
from threading import Thread
import signal
import logging

CLIENT = connect('127.0.0.1', 8000)

class TestCompatibility(unittest.TestCase):
    
    def setUp(self):
        pass 
        
    # Version 2.0 Tests
    
    def test_positional(self):
        """ Positional arguments in a single call """
        result = CLIENT.subtract(23, 42)
        self.assertTrue(result == -19)
        result = CLIENT.subtract(42, 23)
        self.assertTrue(result == 19)
        request = json.loads(history.request)
        response = json.loads(history.response)
        verify_request = {
            "jsonrpc": "2.0", "method": "subtract", 
            "params": [42, 23], "id": request['id']
        }
        verify_response = {
            "jsonrpc": "2.0", "result": 19, "id": request['id']
        }
        self.assertTrue(request == verify_request)
        self.assertTrue(response == verify_response)
        
    def test_named(self):
        """ Named arguments in a single call """
        result = CLIENT.subtract(subtrahend=23, minuend=42)
        self.assertTrue(result == 19)
        result = CLIENT.subtract(minuend=42, subtrahend=23)
        self.assertTrue(result == 19)
        request = json.loads(history.request)
        response = json.loads(history.response)
        verify_request = {
            "jsonrpc": "2.0", "method": "subtract", 
            "params": {"subtrahend": 23, "minuend": 42}, 
            "id": request['id']
        }
        verify_response = {
            "jsonrpc": "2.0", "result": 19, "id": request['id']
        }
        self.assertTrue(request == verify_request)
        self.assertTrue(response == verify_response)
        
    def test_notification(self):
        """ Testing a notification (response should be null) """
        result = CLIENT._notification.update(1, 2, 3, 4, 5)
        self.assertTrue(result == None)
        request = json.loads(history.request)
        response = history.response
        verify_request = {
            "jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]
        }
        verify_response = ''
        self.assertTrue(request == verify_request)
        self.assertTrue(response == verify_response)
        
    def test_non_existent_method(self):
        """ Testing a non existent method (raises -32601) """
        self.assertRaises(ProtocolError, CLIENT.foobar)
        request = json.loads(history.request)
        response = json.loads(history.response)
        verify_request = {
            "jsonrpc": "2.0", "method": "foobar", "id": request['id']
        }
        verify_response = {
            "jsonrpc": "2.0", 
            "error": 
                {"code": -32601, "message": response['error']['message']}, 
            "id": request['id']
        }
        self.assertTrue(request == verify_request)
        self.assertTrue(response == verify_response)
        
    def test_invalid_json(self):
        """ Tests an invalid JSON string (raises -32700) """
        invalid_json = '{"jsonrpc": "2.0", "method": "foobar, '+ \
            '"params": "bar", "baz]'
        response = CLIENT._send_and_receive(invalid_json)
        response = json.loads(history.response)
        verify_response = json.loads(
            '{"jsonrpc": "2.0", "error": {"code": -32700,'+
            ' "message": "Parse error."}, "id": null}'
        )
        verify_response['error']['message'] = response['error']['message']
        self.assertTrue(response == verify_response)
        
    def test_invalid_request(self):
        invalid_request = '{"jsonrpc": "2.0", "method": 1, "params": "bar"}'
        response = CLIENT._send_and_receive(invalid_request)
        response = json.loads(history.response)
        verify_response = json.loads(
            '{"jsonrpc": "2.0", "error": {"code": -32600, '+
            '"message": "Invalid Request."}, "id": null}'
        )
        verify_response['error']['message'] = response['error']['message']
        self.assertTrue(response == verify_response)
        
    def test_batch_invalid_json(self):
        invalid_request = '[ {"jsonrpc": "2.0", "method": "sum", '+ \
            '"params": [1,2,4], "id": "1"},{"jsonrpc": "2.0", "method" ]'
        response = CLIENT._send_and_receive(
            invalid_request, batch=True
        )
        response = json.loads(history.response)
        verify_response = json.loads(
            '{"jsonrpc": "2.0", "error": {"code": -32700,'+
            '"message": "Parse error."}, "id": null}'
        )
        verify_response['error']['message'] = response['error']['message']
        self.assertTrue(response == verify_response)
        
    def test_empty_array(self):
        invalid_request = '[]'
        response = CLIENT._send_and_receive(invalid_request)
        response = json.loads(history.response)
        verify_response = json.loads(
            '{"jsonrpc": "2.0", "error": {"code": -32600, '+
            '"message": "Invalid Request."}, "id": null}'
        )
        verify_response['error']['message'] = response['error']['message']
        self.assertTrue(response == verify_response)
        
    def test_nonempty_array(self):
        invalid_request = '[1,2]'
        request_obj = json.loads(invalid_request)
        response = CLIENT._send_and_receive(invalid_request)
        response = json.loads(history.response)
        self.assertTrue(len(response) == len(request_obj))
        for resp in response:
            verify_resp = json.loads(
                '{"jsonrpc": "2.0", "error": {"code": -32600, '+
                '"message": "Invalid Request."}, "id": null}'
            )
            verify_resp['error']['message'] = resp['error']['message']
            self.assertTrue(resp == verify_resp)
        
    def test_batch(self):
        multicall = CLIENT._batch()
        multicall.sum(1,2,4)
        multicall._notification.notify_hello(7)
        multicall.subtract(42,23)
        multicall.foo.get(name='myself')
        multicall.get_data()
        job_requests = [j._request() for j in multicall._requests]
        job_requests.insert(3, {"foo": "boo"})
        json_requests = '[%s]' % ','.join(
            map(lambda x:json.dumps(x), job_requests)
        )
        requests = json.loads(json_requests)
        response_text = CLIENT._send_and_receive(json_requests, batch=True)
        responses = json.loads(response_text)
        
        verify_requests = json.loads("""[
            {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
            {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
            {"foo": "boo"},
            {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
            {"jsonrpc": "2.0", "method": "get_data", "id": "9"} 
        ]""")
            
        # Thankfully, these are in order so testing is pretty simple.
        verify_responses = json.loads("""[
            {"jsonrpc": "2.0", "result": 7, "id": "1"},
            {"jsonrpc": "2.0", "result": 19, "id": "2"},
            {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request."}, "id": null},
            {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found."}, "id": "5"},
            {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"}
        ]""")
        
        self.assertTrue(len(requests) == len(verify_requests))
        self.assertTrue(len(responses) == len(verify_responses))
        
        responses_by_id = {}
        response_i = 0
        
        for i in range(len(requests)):
            verify_request = verify_requests[i]
            request = requests[i]
            response = None
            if request.get('method') != 'notify_hello':
                req_id = request.get('id')
                if verify_request.has_key('id'):
                    verify_request['id'] = req_id
                verify_response = verify_responses[response_i]
                verify_response['id'] = req_id
                responses_by_id[req_id] = verify_response
                response_i += 1
                response = verify_response
            self.assertTrue(request == verify_request)
            
        for response in responses:
            verify_response = responses_by_id.get(response.get('id'))
            if verify_response.has_key('error'):
                verify_response['error']['message'] = \
                    response['error']['message']
            self.assertTrue(response == verify_response)
        
    def test_batch_notifications(self): 
        multicall = CLIENT._batch()
        multicall._notification.notify_sum(1, 2, 4)
        multicall._notification.notify_hello(7)
        results = multicall()
        result_list = []
        for result in results:
            result_list.append(result)
        self.assertTrue(len(result_list) == 0)
        valid_request = json.loads(
            '[{"jsonrpc": "2.0", "method": "notify_sum", '+
            '"params": [1,2,4]},{"jsonrpc": "2.0", '+
            '"method": "notify_hello", "params": [7]}]'
        )
        request = json.loads(history.request)
        self.assertTrue(len(request) == len(valid_request))
        for i in range(len(request)):
            req = request[i]
            valid_req = valid_request[i]
            self.assertTrue(req == valid_req)
        self.assertTrue(history.response == '')
        
    # Other tests
    
    def test_namespace(self):
        response = CLIENT.namespace.sum(1,2,4)
        request = json.loads(history.request)
        response = json.loads(history.response)
        verify_request = {
            "jsonrpc": "2.0", "params": [1, 2, 4], 
            "id": "5", "method": "namespace.sum"
        }
        verify_response = {
            "jsonrpc": "2.0", "result": 7, "id": "5"
        }
        verify_request['id'] = request['id']
        verify_response['id'] = request['id']
        self.assertTrue(verify_request == request)
        self.assertTrue(verify_response == response)
        
class TestEncryption(unittest.TestCase):
    
    def setUp(self):
        config.secret = '12345abcdef67890'
    
    def test_no_encryption(self):
        crypt = config.crypt
        config.crypt = None
        self.assertRaises(
            EncryptionMissing, connect, 'localhost', 8001, config.secret
        )
        config.crypt = crypt
        
    def test_encryption(self):
        client = connect('localhost', 8001, config.secret)
        result = client.sum(49, 51)
        self.assertTrue(result == 100)
        
    def tearDown(self):
        config.secret = None
        
""" Test Methods """
def subtract(minuend, subtrahend):
    """ Using the keywords from the JSON-RPC v2 doc """
    return minuend-subtrahend
    
def update(*args):
    return args
    
def summation(*args):
    return sum(args)
    
def notify_hello(*args):
    return args
    
def get_data():
    return ['hello', 5]
        
def test_set_up():
    # Because 'setUp' on unittests are called multiple times
    # and starting a server each time is inefficient / a headache
    
    # Starting normal server
    server = Server(('', 8000))
    server.add_handler(summation, 'sum')
    server.add_handler(summation, 'notify_sum')
    server.add_handler(notify_hello)
    server.add_handler(subtract)
    server.add_handler(update)
    server.add_handler(get_data)
    server.add_handler(summation, 'namespace.sum')
    server_proc = Thread(target=server.serve)
    server_proc.daemon = True
    server_proc.start()
    
    #Starting secure server
    server2 = Server(('', 8001))
    server2.add_handler(summation, 'sum')
    server_proc2 = Thread(target=server2.serve)
    server_proc2.daemon = True
    server_proc2.start()
    
    time.sleep(1) # give it time to start up
    #logger.setLevel(logging.DEBUG)
    #logger.addHandler(logging.StreamHandler())

if __name__ == '__main__':
    test_set_up()
    unittest.main()
    
