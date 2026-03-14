# agntrick-whatsapp

WhatsApp integration for Agntrick agents. Connect LLM's to your personal WhatsApp account with QR code login.

## Installation

```bash
pip install agntrick-whatsapp
```

## Features

- **WhatsApp Channel**: Bidirectional communication via personal WhatsApp account
- **QR Code Login**: Easy authentication with your phone
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
# Agent model configuration
model: "glm-4.7"

# Channel configuration
channel:
  storage_path: "./storage"

# Privacy and filtering - only allow your own number
privacy:
  allowed_contact: "+12 6XX X6X XX6"  # Your phone number

# Feature flags
features:
  text_messages: true       # Enable text messages
  media_messages: true      # Enable media (images, videos, documents, audio)
  group_messages: false      # Enable group messages
  presence_updates: true     # Enable presence (online/typing status)
  typing_indicators: true    # Send typing indicators when processing

# WhatsApp bridge settings
whatsapp_bridge:
  auto_setup: true          # Auto-clone Go bridge on first run
  auto_connect: true        # Auto-connect on startup
  bridge_timeout_sec: 180   # Max wait for bridge startup
  poll_interval_sec: 5      # Check for new messages every N seconds

# Logging
logging:
  level: "INFO"              # DEBUG, INFO, WARNING, ERROR
  file: "./logs/agent.log"    # Log file location
```

### 3. Run the WhatsApp Agent

Create a simple Python script `run_whatsapp.py`:

```python
import asyncio
from pathlib import Path
from agntrick_whatsapp import WhatsAppChannel, WhatsAppRouterAgent

async def main():
    # Create channel - storage is where session data is saved
    channel = WhatsAppChannel(
        storage_path="./storage",
        allowed_contact="+34 6XX XXX XXX",  # Your phone number
    )

    # Create and start the router agent
    agent = WhatsAppRouterAgent(
        channel=channel,
        model_name="glm-4.7",
    )

    await agent.start()

asyncio.run(main())
```

Run it:

```bash
python run_whatsapp.py
```

### 4. Scan QR Code

On first run, you'll see a QR code in your terminal. Open WhatsApp on your phone:
1. Go to **Settings** > **Linked Devices**
2. Tap **Link a Device**
3. Scan the QR code

That's it! Your agent is now connected and will respond to messages from your allowed contact.

### Directory Structure Example

Here's how you can organize a project using the `agntrick-whatsapp` package:

```
~/code/agntrick/
├── whatsapp/
│   ├── run_whatsapp.py          # Main entry point
│   ├── whatsapp.yaml            # Configuration file
│   ├── storage/                 # WhatsApp session data (created on first run)
│   └── logs/                   # Application logs
└── prompts/                    # Custom prompts for agents
```

The `storage/` directory contains your WhatsApp session data after QR code login - you don't need to recreate this on subsequent runs.

## First Time Setup

1. **Install system dependencies** (if needed):
   ```bash
   # macOS
   brew install libmagic ffmpeg
   ```

2. **Install the package**:
   ```bash
   pip install agntrick-whatsapp
   ```

3. **Create your config file** (`whatsapp.yaml`):
   - Set your phone number in `allowed_contact`
   - Choose a storage path for session data

4. **Run the agent**:
   ```bash
   python run_whatsapp.py
   ```

5. **Scan the QR code** displayed in your terminal using WhatsApp:
   - Open WhatsApp → Settings → Linked Devices → Link a Device
   - Point your camera at the QR code

6. **Start chatting!** Send a message from your allowed contact number.

### Session Persistence

After the first QR code login, your session is saved in the `storage_path` directory. On subsequent runs, you don't need to scan again - the agent will auto-connect using the saved session.

### Resetting the Session

If you need to re-login (new phone number, etc.), simply delete the storage directory:

```bash
rm -rf ./storage
```

Then run `python run_whatsapp.py` again to scan a new QR code.

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

# Install dependencies with uv (required for this project)
uv sync

# Run tests
make test

# Run linting
make check

# Format code
make format
```

### Using as a Local Package

To use your local development version in another project:

```bash
cd ~/code/agntrick-whatsapp
uv pip install -e .
```

Now your other projects will use your local version.

### Release

```bash
make release VERSION=0.4.0
```

## Troubleshooting

### Import Error: "neonize dependency is unavailable"

Install system dependencies and reinstall:

```bash
# macOS
brew install libmagic
pip install agntrick-whatsapp --force-reinstall

# Ubuntu/Debian
sudo apt-get install libmagic1
pip install agntrick-whatsapp --force-reinstall
```

### QR Code Not Appearing

1. Check storage path permissions - ensure the directory is writable
2. Delete existing session: `rm -rf ./storage` (triggers new QR code on next run)
3. Restart the agent

### Session Lost / Need to Re-login

Delete the storage directory and run again:

```bash
rm -rf ./storage
python run_whatsapp.py
```

### Audio Transcription Not Working

1. Verify Groq API key is set: `echo $GROQ_AUDIO_API_KEY`
2. Check ffmpeg is installed: `ffmpeg -version`
3. Voice messages must be under 25MB

### Messages Not Being Processed

1. Check that your phone number exactly matches `allowed_contact` in config
2. Verify logging level - set to `DEBUG` in config to see what's happening
3. Check logs: `tail -f ./logs/agent.log`

## License

MIT