class Widget:
    """Base widget providing parameter handling and rendering."""

    def __init__(self, **params):
        self.params = params

    def get_param(self, name, default=None, cast=None):
        value = self.params.get(name, default)
        if cast is not None:
            try:
                return cast(value)
            except Exception:
                return default
        return value

    def render(self):
        """Render the widget output. Should be implemented by subclasses."""
        raise NotImplementedError
