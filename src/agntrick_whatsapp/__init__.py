import importlib.metadata

try:
    __version__ = importlib.metadata.version("agntrick-whatsapp")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]
