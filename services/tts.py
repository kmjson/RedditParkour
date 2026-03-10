import re
import asyncio


# Each tuple: (regex pattern, spoken form for TTS, original acronym for subtitles)
_ACRONYM_MAP = [
    (r"\bAITAH\b", "Am I the asshole",    "AITAH"),
    (r"\bAITA\b",  "Am I the asshole",    "AITA"),
    (r"\bNTA\b",   "not the asshole",     "NTA"),
    (r"\bYTA\b",   "you're the asshole",  "YTA"),
    (r"\bESH\b",   "everyone sucks here", "ESH"),
    (r"\bNAH\b",   "no assholes here",    "NAH"),
]


def expand_for_tts(text: str) -> str:
    """Replace Reddit acronyms with their spoken form for the voiceover."""
    for pattern, spoken, _ in _ACRONYM_MAP:
        text = re.sub(pattern, spoken, text, flags=re.IGNORECASE)
    return text


def restore_acronyms_in_subtitles(boundaries: list) -> list:
    """
    Boundary texts contain the expanded spoken form after TTS.
    Swap them back to the original acronym so subtitles show e.g. 'AITAH'
    while the audio says 'Am I the asshole'.
    """
    for b in boundaries:
        for _, spoken, acronym in _ACRONYM_MAP:
            b["text"] = re.sub(re.escape(spoken), acronym, b["text"], flags=re.IGNORECASE)
    return boundaries


async def _run_tts(text: str, audio_path: str) -> list:
    import edge_tts

    communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
    boundaries = []

    with open(audio_path, "wb") as af:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                af.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                boundaries.append({
                    "offset":   chunk["offset"],
                    "duration": chunk["duration"],
                    "text":     chunk["text"],
                })

    return boundaries


def generate_tts(text: str, audio_path: str) -> list:
    """Run async TTS in a fresh event loop (safe to call from threads)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_tts(text, audio_path))
    finally:
        loop.close()
