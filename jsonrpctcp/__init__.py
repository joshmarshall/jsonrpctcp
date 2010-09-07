"""
JSONRPCTCP Library default imports
"""

from jsonrpctcp.config import Config
config = Config.instance()
from jsonrpctcp.history import History
history = History.instance()
from jsonrpctcp.client import connect
from jsonrpctcp.server import start_server
from jsonrpctcp.logger import logger