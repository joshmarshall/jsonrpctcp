"""
This is just the simple config class and singleton for the
JSONRPCTCP library.
"""
   
from ConfigParser import ConfigParser 
CONFIG_SECTION = 'jsonrpctcp'
# For encrypting / decrypting the data on keyed connections.
try:
    from Crypto.Cipher import AES
except:
    AES = None

class Config(object):
    """ Simple object to hold jsonrpctcp configuration options """
    _instance = None
    
    def __init__(self):
        """ The default values for the configuration. """
        self.timeout = 5 # seconds
        self.verbose = False
        self.buffer = 4096
        # 'secret' is used by server to indicate encryption --
        # if it is set, encryption is enabled.
        self.secret = None
        # 'crypt' can be any class anything that implements 'new' and 
        # 'encrypt' / 'decrypt' like they Crypto ciphers.
        self.crypt = AES
        # 'crypt_chunk_size' is the size of the message chunk required 
        # by the cipher.
        self.crypt_chunk_size = 16
        # Maximum number of queued connections
        self.max_queue = 10
    
    @classmethod
    def instance(cls):
        """ Retrieves singleton """
        if not cls._instance:
            cls._instance = cls()
        return cls._instance
        
    def load(self, path):
        """ Loads settings from a configuration file. """
        conf = ConfigParser()
        conf.read(path)
        if not conf.has_section(CONFIG_SECTION):
            return
        for option in conf.options(CONFIG_SECTION):
            value = conf.get(CONFIG_SECTION, option)
            orig_type = type(getattr(self, option, None))
            if type(value) is not orig_type and \
                orig_type is not type(None):
                # Doesn't work for False.
                value = orig_type(value)
            setattr(self, option, value)
