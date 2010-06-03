"""
Sets up the basic logging system for JSONRPCTCP.
"""

import logging

class NullLogHandler(logging.Handler):
    """ Ensures that other libraries don't see 'No handler...' output """
    def emit(self, record):
        pass
        
logger = logging.getLogger('JSONRPCTCP')
logger.addHandler(NullLogHandler())
