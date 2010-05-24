import collections
import time

class Handler(object):
    """
    A simple object that should be populated with methods that handle
    the arguments. Should need little interaction with the JSONRequest
    or Server instance.
    """
    
    def __init__(self, request):
        self.request = request
        
    client_address = None

    @property
    def _handlers(self):
        if not hasattr(self, '__handlers'):
            handlers = {}
            for k in dir(self):
                # Underscores are protected
                if k.startswith('_'):
                    continue
                attr = getattr(self, k)
                # Tree syntax
                if issubclass(type(attr), Handler) and attr != self:
                    for name,handler in attr._handlers.iteritems():
                        name = '%s.%s' % (k, name)
                        handlers[name] = handler
                # Normal syntax
                elif isinstance(attr, collections.Callable):
                    handlers[k] = attr
            self.__handlers = handlers
        return self.__handlers
