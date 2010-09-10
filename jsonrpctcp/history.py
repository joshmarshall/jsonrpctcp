from jsonrpctcp import logger

class History(object):
    """
    This holds the response and request objects for a session.
    """
    _instance = None
    
    def __init__(self):
        self.request = None
        self.response = None
    
    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance