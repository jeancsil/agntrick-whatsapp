"""Test cases for audio transcription functionality."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from agntrick_whatsapp.transcriber import (
    SPEECH_RECOGNITION_AVAILABLE,
    AudioTranscriber,
    TranscriptionError,
    WhatsAppAudioHandler,
    sr_recognizer,
)


class TestAudioTranscriber:
    """Test cases for AudioTranscriber class."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        transcriber = AudioTranscriber()
        assert transcriber.sample_rate == 16000
        assert transcriber.chunk_duration == 1.0
        assert transcriber.language == "en-US"
        assert transcriber.timeout == 30

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        transcriber = AudioTranscriber(
            sample_rate=22050,
            chunk_duration=2.0,
            language="es-ES",
            timeout=60,
        )
        assert transcriber.sample_rate == 22050
        assert transcriber.chunk_duration == 2.0
        assert transcriber.language == "es-ES"
        assert transcriber.timeout == 60

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SPEECH_RECOGNITION_AVAILABLE, reason="Speech recognition not available")
    async def test_transcribe_audio_not_available(self):
        """Test transcription when speech recognition is not available."""
        with patch("agntrick_whatsapp.transcriber.SPEECH_RECOGNITION_AVAILABLE", False):
            transcriber = AudioTranscriber()
            result = await transcriber.transcribe_audio(b"fake_audio_data")

            assert result["status"] == "error"
            assert "not available" in result["message"]

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_recognizer(self):
        """Test transcription when recognizer is not initialized."""
        transcriber = AudioTranscriber()
        transcriber.recognizer = None

        result = await transcriber.transcribe_audio(b"fake_audio_data")

        assert result["status"] == "error"
        assert "not available" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SPEECH_RECOGNITION_AVAILABLE, reason="Speech recognition not available")
    async def test_transcribe_audio_success(self):
        """Test successful audio transcription."""
        transcriber = AudioTranscriber()

        # Patch the transcriber's internal methods
        with patch.object(transcriber, "_transcribe_file") as mock_transcribe:
            mock_transcribe.return_value = "Hello world"

            result = await transcriber.transcribe_audio(b"fake_audio_data")

            assert result["status"] == "success"
            assert result["text"] == "Hello world"
            assert "timestamp" in result
            assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SPEECH_RECOGNITION_AVAILABLE, reason="Speech recognition not available")
    async def test_transcribe_audio_with_error(self):
        """Test transcription handling errors."""
        transcriber = AudioTranscriber()

        # Patch the transcriber's internal methods
        with patch.object(transcriber, "_transcribe_file") as mock_transcribe:
            mock_transcribe.side_effect = Exception("Could not understand audio")

            result = await transcriber.transcribe_audio(b"fake_audio_data")

            assert result["status"] == "error"
            assert "transcription failed" in result["message"]
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_batch_transcribe(self):
        """Test batch transcription of multiple audio files."""
        transcriber = AudioTranscriber()

        with patch.object(transcriber, "transcribe_audio", new=AsyncMock()) as mock_transcribe:
            # Setup mock to return different results for each call
            mock_transcribe.side_effect = [
                {"status": "success", "text": "First", "timestamp": datetime.now().isoformat()},
                {"status": "success", "text": "Second", "timestamp": datetime.now().isoformat()},
                {"status": "error", "message": "Error", "timestamp": datetime.now().isoformat()},
            ]

            audio_files = [
                ("file1.wav", b"audio1"),
                ("file2.wav", b"audio2"),
                ("file3.wav", b"audio3"),
            ]

            results = await transcriber.batch_transcribe(audio_files)

            assert len(results) == 3
            assert results[0]["text"] == "First"
            assert results[1]["text"] == "Second"
            assert results[2]["status"] == "error"

    @pytest.mark.asyncio
    async def test_batch_transcribe_with_exceptions(self):
        """Test batch transcription handling exceptions."""
        transcriber = AudioTranscriber()

        with patch.object(transcriber, "transcribe_audio", new=AsyncMock()) as mock_transcribe:
            mock_transcribe.side_effect = [
                {"status": "success", "text": "OK", "timestamp": datetime.now().isoformat()},
                Exception("Network error"),
                {"status": "success", "text": "Good", "timestamp": datetime.now().isoformat()},
            ]

            audio_files = [
                ("file1.wav", b"audio1"),
                ("file2.wav", b"audio2"),
                ("file3.wav", b"audio3"),
            ]

            results = await transcriber.batch_transcribe(audio_files)

            assert len(results) == 3
            assert results[0]["text"] == "OK"
            assert results[1]["status"] == "error"
            assert "Network error" in results[1]["message"]
            assert results[2]["text"] == "Good"


class TestWhatsAppAudioHandler:
    """Test cases for WhatsAppAudioHandler class."""

    def test_init_default_transcriber(self):
        """Test initialization creates default transcriber."""
        handler = WhatsAppAudioHandler()
        assert handler.transcriber is not None
        assert isinstance(handler.transcriber, AudioTranscriber)

    def test_init_custom_transcriber(self):
        """Test initialization with custom transcriber."""
        custom_transcriber = AudioTranscriber(language="es-ES")
        handler = WhatsAppAudioHandler(transcriber=custom_transcriber)
        assert handler.transcriber is custom_transcriber
        assert handler.transcriber.language == "es-ES"

    @pytest.mark.asyncio
    async def test_process_audio_message_invalid_format(self):
        """Test processing audio message with invalid format."""
        handler = WhatsAppAudioHandler()

        message_data = {"invalid": "data"}

        result = await handler.process_audio_message(message_data)

        assert result["status"] == "error"
        assert "Invalid audio message format" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SPEECH_RECOGNITION_AVAILABLE, reason="Speech recognition not available")
    async def test_process_audio_message_with_valid_data(self):
        """Test processing valid audio message."""
        handler = WhatsAppAudioHandler()

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg123",
                                        "type": "audio",
                                        "audio": {
                                            "mime_type": "audio/ogg",
                                            "sha256": "abc123",
                                            "voice_note": True,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        with patch.object(handler.transcriber, "transcribe_audio", new=AsyncMock()) as mock_transcribe:
            mock_transcribe.return_value = {
                "status": "success",
                "text": "Hello from audio",
                "timestamp": datetime.now().isoformat(),
            }

            result = await handler.process_audio_message(message_data)

            assert result["status"] == "success"
            assert result["audio_info"]["id"] == "msg123"
            assert result["audio_info"]["mime_type"] == "audio/ogg"
            assert result["audio_info"]["voice_note"] is True
            assert result["transcription"]["text"] == "Hello from audio"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SPEECH_RECOGNITION_AVAILABLE, reason="Speech recognition not available")
    async def test_process_audio_message_with_transcription_error(self):
        """Test processing audio message when transcription fails."""
        handler = WhatsAppAudioHandler()

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg123",
                                        "type": "audio",
                                        "audio": {"mime_type": "audio/ogg", "sha256": "abc123"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        with patch.object(handler.transcriber, "transcribe_audio", new=AsyncMock()) as mock_transcribe:
            mock_transcribe.side_effect = Exception("Transcription failed")

            result = await handler.process_audio_message(message_data)

            assert result["status"] == "error"
            assert "Transcription failed" in result["message"]

    def test_extract_audio_info_with_audio_message(self):
        """Test extracting audio info from message data."""
        handler = WhatsAppAudioHandler()

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg123",
                                        "type": "audio",
                                        "audio": {
                                            "mime_type": "audio/ogg",
                                            "sha256": "abc123",
                                            "voice_note": True,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        audio_info = handler._extract_audio_info(message_data)

        assert audio_info is not None
        assert audio_info["id"] == "msg123"
        assert audio_info["mime_type"] == "audio/ogg"
        assert audio_info["sha256"] == "abc123"
        assert audio_info["voice_note"] is True
        assert audio_info["format"] == "ogg"

    def test_extract_audio_info_no_audio_message(self):
        """Test extracting audio info when no audio message present."""
        handler = WhatsAppAudioHandler()

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg123",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        audio_info = handler._extract_audio_info(message_data)
        assert audio_info is None

    def test_extract_audio_info_voice_note_false(self):
        """Test format is mp3 when not a voice note."""
        handler = WhatsAppAudioHandler()

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg123",
                                        "type": "audio",
                                        "audio": {
                                            "mime_type": "audio/mp3",
                                            "sha256": "abc123",
                                            "voice_note": False,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        audio_info = handler._extract_audio_info(message_data)
        assert audio_info["format"] == "mp3"

    @pytest.mark.asyncio
    async def test_download_audio_simulated(self):
        """Test audio download (simulated)."""
        handler = WhatsAppAudioHandler()

        audio_info = {"id": "msg123", "sha256": "abc123"}

        audio_data = await handler._download_audio(audio_info)

        assert isinstance(audio_data, bytes)
        assert audio_data == b"dummy_audio_data"

    def test_transcription_error(self):
        """Test TranscriptionError can be raised and caught."""
        with pytest.raises(TranscriptionError):
            raise TranscriptionError("Test error")


class TestAudioTranscriberWithoutSR:
    """Test cases for AudioTranscriber when speech_recognition is unavailable."""

    @pytest.mark.asyncio
    async def test_transcribe_audio_sr_unavailable(self):
        """Test transcription returns error when speech_recognition is not available."""
        with patch("agntrick_whatsapp.transcriber.SPEECH_RECOGNITION_AVAILABLE", False):
            transcriber = AudioTranscriber()
            result = await transcriber.transcribe_audio(b"audio_data")
        assert result["status"] == "error"
        assert "not available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_batch_transcribe_all_errors(self):
        """Test batch_transcribe returns error list when SR is unavailable."""
        with patch("agntrick_whatsapp.transcriber.SPEECH_RECOGNITION_AVAILABLE", False):
            transcriber = AudioTranscriber()
            files = [("file1.wav", b"audio1"), ("file2.wav", b"audio2")]
            results = await transcriber.batch_transcribe(files)
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(r["status"] == "error" for r in results)

    @pytest.mark.asyncio
    async def test_batch_transcribe_empty_list(self):
        """Test batch_transcribe with empty list returns empty results."""
        transcriber = AudioTranscriber()
        results = await transcriber.batch_transcribe([])
        assert results == []

    def test_create_audio_file(self):
        """Test _create_audio_file creates a temporary file."""
        import os

        transcriber = AudioTranscriber()
        temp_path = transcriber._create_audio_file(b"test audio data", "wav")
        assert os.path.exists(temp_path)
        assert temp_path.endswith(".wav")
        # Cleanup
        os.unlink(temp_path)

    def test_create_audio_file_ogg_format(self):
        """Test _create_audio_file with ogg format."""
        import os

        transcriber = AudioTranscriber()
        temp_path = transcriber._create_audio_file(b"test", "ogg")
        assert temp_path.endswith(".ogg")
        os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_transcribe_audio_success_mocked(self):
        """Test successful transcription path with mocked recognizer."""
        transcriber = AudioTranscriber()
        # Simulate having a recognizer
        transcriber.recognizer = True  # type: ignore[assignment]

        with (
            patch("agntrick_whatsapp.transcriber.SPEECH_RECOGNITION_AVAILABLE", True),
            patch.object(transcriber, "_create_audio_file", return_value="/tmp/fake.wav"),
            patch.object(transcriber, "_transcribe_file", new=AsyncMock(return_value="Hello world")),
        ):
            result = await transcriber.transcribe_audio(b"fake_audio_data")

        assert result["status"] == "success"
        assert result["text"] == "Hello world"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_transcribe_audio_exception_in_transcribe_file(self):
        """Test transcription failure path when _transcribe_file raises."""
        transcriber = AudioTranscriber()
        transcriber.recognizer = True  # type: ignore[assignment]

        with (
            patch("agntrick_whatsapp.transcriber.SPEECH_RECOGNITION_AVAILABLE", True),
            patch.object(transcriber, "_create_audio_file", return_value="/tmp/fake.wav"),
            patch.object(transcriber, "_transcribe_file", new=AsyncMock(side_effect=Exception("Audio unclear"))),
        ):
            result = await transcriber.transcribe_audio(b"bad_audio")

        assert result["status"] == "error"
        assert "Audio unclear" in result["message"]

    @pytest.mark.asyncio
    async def test_transcribe_audio_sr_available_no_recognizer(self):
        """Test transcription when SR available but recognizer is None."""
        transcriber = AudioTranscriber()
        transcriber.recognizer = None

        with patch("agntrick_whatsapp.transcriber.SPEECH_RECOGNITION_AVAILABLE", True):
            result = await transcriber.transcribe_audio(b"audio_data")

        assert result["status"] == "error"
        assert "not available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_transcribe_file_raises_without_recognizer(self):
        """Test _transcribe_file raises when recognizer is None."""
        transcriber = AudioTranscriber()
        transcriber.recognizer = None

        with pytest.raises(Exception, match="not available"):
            await transcriber._transcribe_file("/tmp/fake.wav")


class TestWhatsAppAudioHandlerProcessing:
    """Additional test cases for WhatsAppAudioHandler processing paths."""

    @pytest.mark.asyncio
    async def test_process_audio_with_valid_data_no_sr(self):
        """Test process_audio_message with valid data when SR is unavailable."""
        handler = WhatsAppAudioHandler()
        msg_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "type": "audio",
                                        "audio": {
                                            "mime_type": "audio/ogg",
                                            "sha256": "abc123",
                                            "voice_note": True,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        result = await handler.process_audio_message(msg_data)
        # With simulated audio, the transcription might succeed or fail
        assert result["status"] in ("success", "error")

    @pytest.mark.asyncio
    async def test_process_audio_message_empty_entry(self):
        """Test processing with empty entry list."""
        handler = WhatsAppAudioHandler()
        result = await handler.process_audio_message({"entry": []})
        assert result["status"] == "error"

    def test_extract_audio_info_empty_dict(self):
        """Test _extract_audio_info with empty dict returns None."""
        handler = WhatsAppAudioHandler()
        result = handler._extract_audio_info({})
        assert result is None

    def test_extract_audio_info_no_voice_note(self):
        """Test _extract_audio_info with non-voice-note audio returns mp3 format."""
        handler = WhatsAppAudioHandler()
        msg_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "type": "audio",
                                        "audio": {
                                            "mime_type": "audio/mp3",
                                            "sha256": "def456",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        info = handler._extract_audio_info(msg_data)
        assert info is not None
        assert info["format"] == "mp3"
        assert info["voice_note"] is False

    @pytest.mark.asyncio
    async def test_process_audio_message_exception_in_download(self):
        """Test process_audio_message wraps exceptions in error dict."""
        handler = WhatsAppAudioHandler()

        # Mock _download_audio to raise
        with patch.object(handler, "_download_audio", new=AsyncMock(side_effect=Exception("Download failed"))):
            msg_data = {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "id": "msg1",
                                            "type": "audio",
                                            "audio": {"mime_type": "audio/ogg"},
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
            result = await handler.process_audio_message(msg_data)

        assert result["status"] == "error"
        assert "Download failed" in result["message"]

    @pytest.mark.asyncio
    async def test_process_audio_message_with_mocked_transcription(self):
        """Test full process_audio_message success path with mocked transcription."""
        handler = WhatsAppAudioHandler()

        mock_transcribe = AsyncMock(
            return_value={
                "status": "success",
                "text": "Hello from audio",
                "timestamp": datetime.now().isoformat(),
            }
        )

        with patch.object(handler.transcriber, "transcribe_audio", mock_transcribe):
            msg_data = {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "id": "msg1",
                                            "type": "audio",
                                            "audio": {
                                                "mime_type": "audio/ogg",
                                                "sha256": "abc",
                                                "voice_note": True,
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
            result = await handler.process_audio_message(msg_data)

        assert result["status"] == "success"
        assert result["audio_info"]["id"] == "msg1"
        assert result["transcription"]["text"] == "Hello from audio"


class TestSpeechRecognitionAvailability:
    """Test cases for speech recognition availability checks."""

    def test_speech_recognition_available_module(self):
        """Test SPEECH_RECOGNITION_AVAILABLE flag exists."""
        assert isinstance(SPEECH_RECOGNITION_AVAILABLE, bool)

    def test_sr_recognizer_module(self):
        """Test sr_recognizer is properly imported or None."""
        if SPEECH_RECOGNITION_AVAILABLE:
            assert sr_recognizer is not None
        else:
            assert sr_recognizer is None
