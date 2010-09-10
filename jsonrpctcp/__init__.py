"""
JSONRPCTCP Library default imports
"""

__all__ = ['config', 'history', 'connect', 'logger', 'start_server']

# Set up the basic logging system for JSONRPCTCP.
import logging

class NullLogHandler(logging.Handler):
    """ Ensures that other libraries don't see 'No handler...' output """
    def emit(self, record):
        pass
        
logger = logging.getLogger('JSONRPCTCP')
logger.addHandler(NullLogHandler())

# Default imports
from jsonrpctcp.config import Config
config = Config.instance()
from jsonrpctcp.history import History
history = History.instance()
from jsonrpctcp.client import connect
from jsonrpctcp.server import start_server