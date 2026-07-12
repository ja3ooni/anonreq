import asyncio
from collections.abc import AsyncGenerator

import numpy as np
import structlog
import torch
import whisper

logger = structlog.get_logger(__name__)

class LocalSTTEngine:
    """Self-hosted Whisper model inference engine for streaming transcription.

    Handles GPU acceleration detection and fallback to CPU.
    Produces streaming transcription with overlapping chunk assembly.
    """

    def __init__(self, model_size: str = "tiny"):
        self.model_size = model_size
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = None
        self._lock = asyncio.Lock()

    async def load_model(self) -> None:
        """Load the Whisper model into memory."""
        async with self._lock:
            if self._model is None:
                logger.info(f"Loading Whisper {self.model_size} model on {self.device}")
                # Run load in executor to avoid blocking the event loop
                loop = asyncio.get_running_loop()
                self._model = await loop.run_in_executor(
                    None,
                    lambda: whisper.load_model(self.model_size, device=self.device)
                )
                logger.info("Whisper model loaded successfully")

    async def transcribe_chunk(self, audio_data: np.ndarray) -> str:
        """Transcribe a chunk of audio data.

        Args:
            audio_data: Numpy array of audio data (16kHz mono).

        Returns:
            The transcribed text.
        """
        if self._model is None:
            await self.load_model()

        loop = asyncio.get_running_loop()
        # Run inference in executor
        result = await loop.run_in_executor(
            None,
            lambda: self._model.transcribe(audio_data, fp16=False)
        )
        return result.get("text", "").strip()

    async def stream_transcribe(self, audio_stream: AsyncGenerator[np.ndarray, None]) -> AsyncGenerator[str, None]:  # noqa: E501
        """Stream transcription from an async generator of audio chunks."""
        async for chunk in audio_stream:
            text = await self.transcribe_chunk(chunk)
            if text:
                yield text
