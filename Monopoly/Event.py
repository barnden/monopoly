import functools

class Event:
    def __init__(self, message):
        self.message = message

    def __str__(self):
        fields = []

        for key, val in self.__dict__.items():
            fields.append(f"{key}={val}")

        fields = ", ".join(fields)

        return f"{self.__class__.__name__}({fields})"

class PlayerEvent(Event):
    def __init__(self, player):
        self.player = player

class PlayerMoveEvent(PlayerEvent):
    def __init__(self, player, initial, final, teleport=False):
        super().__init__(player)
        self.initial = initial
        self.final = final
        self.teleport = teleport

class PropertyPurchaseEvent(PlayerEvent):
    def __init__(self, player, tile):
        super().__init__(player)
        self.tile = tile

class TurnEnd(Event):
    def __init__(self, player):
        self.player = player

class TurnStart(Event):
    def __init__(self, player):
        self.player = player

class EventDispatcher:
    def __init__(self):
        self.handlers = {}

    def add_handler(self, event, handler):
        if not hasattr(handler, "__iter__"):
            handler = [handler]

        if not hasattr(event, "__iter__"):
            event = [event]

        # Event is root object of all events, collapse to avoid duplication
        if Event in event:
            event = [Event]

        for e in event:
            if e not in self.handlers:
                self.handlers[e] = handler
            else:
                self.handlers[e] += handler

    def __ior__(self, args):
        if len(args) != 2:
            raise ValueError(f"[EventDispatcher] event listener expected two arguments (Events, handler), got {len(args)} instead.")
        
        self.add_handler(*args)

        return self

    def __iadd__(self, obj):
        if not isinstance(obj, Event):
            raise TypeError(f"[EventDispatcher] expected instance of {Event}, got instead {type(obj)}")

        if Event in self.handlers:
            for handler in self.handlers[Event]:
                handler(obj)

        if type(obj) == Event:
            return self

        if type(obj) not in self.handlers:
            print(f"[EventDispatcher] event {obj} has no handlers")

            return self

        for handler in self.handlers[type(obj)]:
            handler(obj)

        return self

def bindlisteners(cls):
    """
    Class decorator.

    Looks for methods decorated with "listen" and adds the method as
    an event handler for the instance's EventDispatcher.
    """
    @functools.wraps(cls)
    def create(*args, **kwargs):
        instance = cls(*args, **kwargs)

        # Check for any methods decorated with "eventhandler"
        # If so, add the method as an event handler with the associated event
        for fname in dir(instance):
            func = getattr(instance, fname)

            if not callable(func):
                continue

            # walrus (:3 っ)っ ;)
            if event := getattr(func, "_event", None):
                instance.events |= event, func

        return instance
    return create

def listen(*events):
    def handler(func):
        setattr(func, "_event", events)
        return func
    
    return handler