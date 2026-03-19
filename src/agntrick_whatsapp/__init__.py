import importlib.metadata

try:
    __version__ = importlib.metadata.version("agntrick-whatsapp")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

from agntrick_whatsapp.base import (
    BaseWhatsAppMessage,
    TextMessage,
    WhatsAppChannelBase,
    WhatsAppMessageStatus,
    WhatsAppMessageType,
)
from agntrick_whatsapp.channel import WhatsAppChannel
from agntrick_whatsapp.router import WhatsAppRouterAgent
from agntrick_whatsapp.runner_config import WhatsAppRunnerSettings, load_settings

__all__ = [
    "__version__",
    "BaseWhatsAppMessage",
    "TextMessage",
    "WhatsAppChannel",
    "WhatsAppChannelBase",
    "WhatsAppMessageStatus",
    "WhatsAppMessageType",
    "WhatsAppRouterAgent",
    "WhatsAppRunnerSettings",
    "load_settings",
]
