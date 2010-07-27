"""
This is just the simple config class and singleton for the
JSONRPCTCP library.
"""

class Config(object):
    """ Simple object to hold jsonrpctcp configuration options """
    _instance = None
    
    def __init__(self):
        """ The default values for the configuration. """
        self.timeout = 5 # seconds
        self.verbose = False
        self.buffer = 1024
    
    @classmethod
    def instance(cls):
        """ Retrieves singleton """
        if not cls._instance:
            cls._instance = cls()
        return cls._instance
    
config = Config.instance()
