# agntrick-whatsapp

WhatsApp integration for Agntrick agents.

## Installation

```bash
pip install agntrick-whatsapp
```

## Features

- **WhatsApp Channel**: Bidirectional communication via personal WhatsApp account
- **Router Agent**: Routes messages to different specialist modes based on commands
- **Audio Transcription**: Transcribe voice messages using Groq Whisper API
- **Contact Filtering**: Privacy-focused with allowed contacts only
- **Scheduling**: Schedule reminders and agent tasks with natural language time parsing
- **Notes**: Save and retrieve notes through WhatsApp

## Requirements

### System Dependencies

The WhatsApp channel uses `neonize` which requires:
- **libmagic**: For file type detection
  - macOS: `brew install libmagic`
  - Ubuntu/Debian: `sudo apt-get install libmagic1`
  - Fedora: `sudo dnf install file-devel`

### Audio Transcription (Optional)

For audio transcription, you need:
- **ffmpeg**: For audio format conversion
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Fedora: `sudo dnf install ffmpeg`

- **Groq API Key**: Set `GROQ_AUDIO_API_KEY` or `GROQ_API_KEY` environment variable

## Quick Start

### 1. Install Dependencies

```bash
pip install agntrick-whatsapp
```

### 2. Create Configuration

Create a `whatsapp.yaml` configuration file:

```yaml
model: claude-sonnet-4-6
mcp_servers: ["fetch", "web-forager"]

privacy:
  allowed_contact: "+1234567890"  # Your phone number

channel:
  storage_path: ~/storage/whatsapp

features:
  text_messages: true
  media_messages: true
  group_messages: false
  typing_indicators: true

audio_transcriber:
  model: whisper-large-v3-turbo
  timeout: 60.0
```

### 3. Run the WhatsApp Agent

```python
import asyncio
from pathlib import Path
import yaml
from agntrick_whatsapp import WhatsAppChannel, WhatsAppRouterAgent
from agntrick_whatsapp.config import WhatsAppAgentConfig

async def main():
    # Load configuration from YAML
    config_path = Path(__file__).parent / "whatsapp.yaml"
    with open(config_path) as f:
        config_dict = yaml.safe_load(f)

    config = WhatsAppAgentConfig.model_validate(config_dict)

    # Create channel
    channel = WhatsAppChannel(
        storage_path=config.get_storage_path(),
        allowed_contact=config.privacy.allowed_contact,
    )

    # Create router agent
    agent = WhatsAppRouterAgent(
        channel=channel,
        model_name=config.model,
        mcp_servers_override=config.mcp_servers,
        audio_transcriber_config=config.audio_transcriber,
    )

    # Start listening
    await agent.start()

asyncio.run(main())
```

## Commands

The router agent supports the following commands:

| Command | Description |
|---------|-------------|
| `/learn <topic>` | Learning/tutorial mode |
| `/youtube <url>` | YouTube video analysis |
| `/remind <time> <message>` | Set a reminder |
| `/schedule <time> <agent> [task]` | Schedule an agent task |
| `/schedules` | List all scheduled tasks |
| `/note <content>` | Save a note |
| `/notes` | List all saved notes |
| `/help` | Show available commands |

### Examples

- `/learn Python decorators` - Get a step-by-step tutorial on Python decorators
- `/youtube https://youtube.com/watch?v=xyz` - Analyze a YouTube video
- `/remind in 30 min check the oven` - Set a reminder
- `/schedule tomorrow 9am assistant summarize news` - Schedule a task
- `/note Remember to call mom` - Save a note
- `What's the weather in Tokyo?` - General question

## Audio Transcription

Voice messages are automatically transcribed using Groq's Whisper API:

```python
from agntrick_whatsapp import AudioTranscriber

transcriber = AudioTranscriber()
result = await transcriber.transcribe_audio("/path/to/voice.ogg")
print(result)
```

## Configuration Reference

### PrivacyConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `allowed_contact` | str | Yes | Phone number to allow messages from |
| `log_filtered_messages` | bool | No | Log filtered messages for debugging |

### FeatureFlags

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text_messages` | bool | true | Enable text messages |
| `media_messages` | bool | true | Enable media messages |
| `group_messages` | bool | false | Enable group messages |
| `presence_updates` | bool | true | Enable presence updates |
| `typing_indicators` | bool | true | Send typing indicators |

### AudioTranscriberConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | str | whisper-large-v3-turbo | Groq Whisper model |
| `timeout` | float | 60.0 | Request timeout in seconds |
| `config_file` | str? | None | Optional config file path |

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/jeancsil/agntrick-whatsapp.git
cd agntrick-whatsapp

# Install dependencies with uv
uv sync

# Run tests
make test

# Run linting
make check
```

### Release

```bash
make release VERSION=0.4.0
```

## Troubleshooting

### neonize Import Error

```
RuntimeError: neonize dependency is unavailable
```

Install system dependencies (libmagic) and reinstall:
```bash
brew install libmagic  # macOS
pip install agntrick-whatsapp --force-reinstall
```

### QR Code Not Appearing

1. Check storage path permissions
2. Delete existing session: `rm -rf ~/storage/whatsapp` (take care with this and always ask the user)
3. Restart the agent

### Audio Transcription Fails

1. Verify Groq API key: `echo $GROQ_AUDIO_API_KEY`
2. Check ffmpeg: `ffmpeg -version`
3. Check file size (max 25MB)

## License

MIT