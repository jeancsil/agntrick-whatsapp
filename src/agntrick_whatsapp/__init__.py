"""WhatsApp integration for Agntrick framework."""

from .base import BaseWhatsAppMessage, TextMessage, WhatsAppChannelBase, WhatsAppMessageStatus, WhatsAppMessageType
from .channel import WhatsAppChannel
from .commands import CommandHandler, CommandParser, CommandType, ParsedCommand
from .config import AgentConfig, StorageConfig, WebhookConfig, WhatsAppConfig, WhatsAppRouterConfig
from .router import WhatsAppRouterAgent
from .transcriber import AudioTranscriber, WhatsAppAudioHandler

__all__ = [
    # Base classes
    "BaseWhatsAppMessage",
    "TextMessage",
    "WhatsAppChannelBase",
    "WhatsAppMessageStatus",
    "WhatsAppMessageType",
    # Channel
    "WhatsAppChannel",
    # Commands
    "CommandHandler",
    "CommandParser",
    "ParsedCommand",
    "CommandType",
    # Configuration
    "WhatsAppConfig",
    "WhatsAppRouterConfig",
    "AgentConfig",
    "StorageConfig",
    "WebhookConfig",
    # Router
    "WhatsAppRouterAgent",
    # Transcription
    "AudioTranscriber",
    "WhatsAppAudioHandler",
]
