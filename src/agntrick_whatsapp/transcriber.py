"""Audio transcription functionality for WhatsApp messages."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False


class AudioTranscriber:
    """Handles transcription of audio messages from WhatsApp."""

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration: float = 1.0,
        language: str = "en-US",
        timeout: int = 30
    ):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.language = language
        self.timeout = timeout

        # Initialize speech recognition if available
        self.recognizer = sr.Recognizer() if SPEECH_RECOGNITION_AVAILABLE else None

    async def transcribe_audio(
        self,
        audio_data: bytes,
        format: str = "wav"
    ) -> Dict[str, Any]:
        """Transcribe audio data to text."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            return {
                "status": "error",
                "message": "Speech recognition library not available. Install with: pip install SpeechRecognition"
            }

        try:
            # Create audio file from bytes
            audio_file = self._create_audio_file(audio_data, format)

            # Perform transcription
            text = await self._transcribe_file(audio_file)

            return {
                "status": "success",
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.0  # Would be populated by actual recognition
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Transcription failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _create_audio_file(self, audio_data: bytes, format: str) -> Any:
        """Create audio file from bytes data."""
        import tempfile
        import os

        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as temp_file:
            temp_file.write(audio_data)
            return temp_file.name

    async def _transcribe_file(self, audio_file_path: str) -> str:
        """Transcribe audio file using speech recognition."""
        with sr.AudioFile(audio_file_path) as source:
            # Adjust for ambient noise
            audio = self.recognizer.record(source)

            try:
                # Try to transcribe using Google Speech Recognition
                text = self.recognizer.recognize_google(
                    audio,
                    language=self.language
                )
                return text
            except sr.UnknownValueError:
                raise Exception("Could not understand audio")
            except sr.RequestError as e:
                raise Exception(f"Speech recognition service error: {e}")

    async def batch_transcribe(
        self,
        audio_files: List[Tuple[str, bytes]]
    ) -> List[Dict[str, Any]]:
        """Transcribe multiple audio files concurrently."""
        tasks = []
        for file_name, audio_data in audio_files:
            task = self.transcribe_audio(audio_data)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "status": "error",
                    "message": str(result),
                    "file": audio_files[i][0],
                    "timestamp": datetime.now().isoformat()
                })
            else:
                processed_results.append(result)

        return processed_results


class WhatsAppAudioHandler:
    """Handles audio messages from WhatsApp."""

    def __init__(self, transcriber: Optional[AudioTranscriber] = None):
        self.transcriber = transcriber or AudioTranscriber()

    async def process_audio_message(
        self,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process an incoming audio message from WhatsApp."""
        try:
            # Extract audio information from message
            audio_info = self._extract_audio_info(message_data)
            if not audio_info:
                return {
                    "status": "error",
                    "message": "Invalid audio message format"
                }

            # Download audio if needed (in real implementation)
            # For now, we'll simulate having the audio data
            audio_data = await self._download_audio(audio_info)

            # Transcribe the audio
            transcription = await self.transcriber.transcribe_audio(
                audio_data,
                audio_info.get("format", "wav")
            )

            # Create text message from transcription
            text_message = {
                "type": "text",
                "text": transcription.get("text", ""),
                "original_audio": audio_info,
                "transcription_result": transcription
            }

            return {
                "status": "success",
                "message": text_message,
                "audio_info": audio_info,
                "transcription": transcription
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error processing audio message: {str(e)}",
                "details": str(e)
            }

    def _extract_audio_info(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract audio information from WhatsApp message data."""
        try:
            messages = message_data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])

            for message in messages:
                if message.get("type") == "audio":
                    audio = message.get("audio", {})
                    return {
                        "id": message.get("id"),
                        "mime_type": audio.get("mime_type"),
                        "sha256": audio.get("sha256"),
                        "voice_note": audio.get("voice_note", False),
                        "format": "ogg" if audio.get("voice_note") else "mp3"
                    }
            return None
        except Exception:
            return None

    async def _download_audio(self, audio_info: Dict[str, Any]) -> bytes:
        """Download audio data (simulated)."""
        # In a real implementation, this would make API calls to WhatsApp
        # to download the audio file using the SHA256 hash
        await asyncio.sleep(0.1)  # Simulate download
        return b"dummy_audio_data"  # Placeholder


class TranscriptionError(Exception):
    """Exception raised during transcription errors."""
    pass