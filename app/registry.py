class Registry:
    """
    Simple registry for nodes or reusable functions.
    Useful if you later want dynamic node resolution.
    """

    def __init__(self):
        self._items = {}

    def register(self, name: str, fn):
        self._items[name] = fn

    def get(self, name: str):
        return self._items.get(name)

    def all(self):
        return self._items
