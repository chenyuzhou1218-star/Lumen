"""A tiny event bus."""

_handlers = {}


def subscribe(event, fn):
    _handlers.setdefault(event, {})[fn.__name__] = fn


def emit(event, **payload):
    for fn in list(_handlers.get(event, {}).values()):
        fn(**payload)
