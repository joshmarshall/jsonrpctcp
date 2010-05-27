import logging

# Ensures that other libraries don't see 'No handler...' output

class NullLogHandler(logging.Handler):
    def emit(self, record):
        pass
        
logger = logging.getLogger('JSONRPCTCP')
logger.addHandler(NullLogHandler())
