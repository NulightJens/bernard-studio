"""One error type for things Bernard can act on: the message is one plain sentence (what went wrong, what to do)."""


class StudioError(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code
