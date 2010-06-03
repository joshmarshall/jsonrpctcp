"""
This is just the simple config class and singleton for the
JSONRPCTCP library.
"""

class Config(object):
    """ The default values for the configuration. """
    timeout = 5 # seconds
    verbose = False
    buffer = 1024
    
config = Config()
