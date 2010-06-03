"""
The Handler class, which can be nested. This should be attached to a
Server instance.
"""

class Handler(object):
    """
    A simple object that should be populated with methods that handle
    the arguments. Should need little interaction with the JSONRequest
    or Server instance.
    """
    
    def __init__(self, request):
        self.request = request
        self.__handlers = None
        
    client_address = None

    @property
    def _handlers(self):
        """
        Parses the Handler instance to find all callables which aren't
        protected (starts with '_'), or instances of Handler.
        """
        if not self.__handlers:
            handlers = {}
            for key in dir(self):
                # Underscores are protected
                if key.startswith('_'):
                    continue
                attr = getattr(self, key)
                # Tree syntax
                if issubclass(type(attr), Handler) and attr != self:
                    for name, handler in attr._handlers.iteritems():
                        name = '%s.%s' % (key, name)
                        handlers[name] = handler
                # Normal syntax
                elif hasattr(attr, '__call__'):
                    handlers[key] = attr
            self.__handlers = handlers
        return self.__handlers
