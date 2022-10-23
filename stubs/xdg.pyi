XDG_CONFIG_HOME: str


class BaseDirectory:
    @classmethod
    def save_data_path(cls, name: str) -> str: ...
