"""Voice turn pipeline: listen → transcribe → agent → vocalize → play.

The pipeline keeps voice I/O outside the core reasoning loop: the agent
only ever sees text. Every stage is replaceable through the provider ABCs.
"""

from __future__ import annotations

from .providers import SpeechInput, SpeechOutput, Transcriber, Vocalizer, VoiceError


def voice_turn(
    transcript_source,
    *,
    speech_input: SpeechInput,
    transcriber: Transcriber,
    vocalizer: Vocalizer,
    speech_output: SpeechOutput,
    timeout_s: float | None = None,
    source: str = "voice",
) -> str:
    """Run one full voice turn; return the agent's reply text.

    ``transcript_source`` receives the transcript (plus ``source=``) and
    returns an object with ``.content`` — normally a small wrapper around
    ``Agent.process`` with a :class:`Request`. Raises :class:`VoiceError`
    when any stage fails.
    """
    try:
        frame = speech_input.listen(timeout_s=timeout_s)
        transcript = transcriber.transcribe(frame, timeout_s=timeout_s)
    except VoiceError:
        raise
    except Exception as exc:
        raise VoiceError(f"voice input failed: {exc}") from exc
    if not transcript.text.strip():
        raise VoiceError("empty transcript")
    try:
        response = transcript_source(transcript.text, source=source)
    except Exception as exc:
        raise VoiceError(f"agent turn failed: {exc}") from exc
    content = getattr(response, "content", "")
    if not (isinstance(content, str) and content.strip()):
        raise VoiceError("agent produced no reply")
    try:
        audio = vocalizer.vocalize(content, timeout_s=timeout_s)
        speech_output.play(audio, timeout_s=timeout_s)
    except VoiceError:
        raise
    except Exception as exc:
        raise VoiceError(f"voice output failed: {exc}") from exc
    return content
