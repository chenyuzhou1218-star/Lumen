class App:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def register(fn):
            self.routes[("POST", path)] = fn
            return fn
        return register


app = App()
