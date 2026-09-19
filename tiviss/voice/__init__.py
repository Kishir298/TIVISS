"""Replaceable voice abstraction for T.I.V.I.S.S.

Voice input, processing, and output are separated so the core reasoning
loop never depends on audio hardware or ML libraries. The runtime ships
with deterministic mocks; real engines implement the same ABCs.
"""

from .mock import (
    MockSpeechInput,
    MockSpeechOutput,
    MockTranscriber,
    MockVocalizer,
)
from .pipeline import voice_turn
from .providers import (
    AudioFrame,
    SpeechInput,
    SpeechOutput,
    Transcriber,
    Transcript,
    Vocalizer,
    VoiceError,
)

__all__ = [
    "AudioFrame",
    "SpeechInput",
    "SpeechOutput",
    "Transcript",
    "Transcriber",
    "Vocalizer",
    "VoiceError",
    "MockSpeechInput",
    "MockSpeechOutput",
    "MockTranscriber",
    "MockVocalizer",
    "voice_turn",
]
