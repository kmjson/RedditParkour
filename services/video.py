import os
import shutil
import subprocess
import tempfile

import imageio_ffmpeg
from mutagen.mp3 import MP3

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR   = os.path.join(PROJECT_DIR, "static", "fonts")
FONT_FILE   = "Nunito-Bold.ttf"
FONT_NAME   = "Nunito"
FONT_PATH   = os.path.join(FONTS_DIR, FONT_FILE)


def get_audio_duration(audio_path: str) -> float:
    try:
        return MP3(audio_path).info.length
    except Exception:
        return 60.0


def _split_lines(text: str, max_chars: int = 38) -> list[str]:
    """
    Break text into lines of at most max_chars, splitting on word boundaries.
    After the initial greedy fill, balance the last two lines by moving words
    from the end of the penultimate line to prevent orphaned short last lines.
    """
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current: list[str] = []
    cur_len = 0
    for word in words:
        needed = cur_len + (1 if current else 0) + len(word)
        if needed <= max_chars:
            current.append(word)
            cur_len = needed
        else:
            if current:
                lines.append(" ".join(current))
            current, cur_len = [word], len(word)
    if current:
        lines.append(" ".join(current))

    if not lines:
        return [text]

    while len(lines) >= 2:
        prev_words = lines[-2].split()
        if len(prev_words) <= 1:
            break
        candidate = prev_words[-1] + " " + lines[-1]
        if len(candidate) > max_chars or len(candidate) > len(lines[-2]):
            break
        lines[-2] = " ".join(prev_words[:-1])
        lines[-1] = candidate

    return lines


def _ass_time(offset_100ns: int) -> str:
    """Convert an edge-tts 100 ns offset to ASS time format H:MM:SS.cs"""
    total_cs = offset_100ns // 100_000
    cs = total_cs % 100
    s  = (total_cs // 100) % 60
    m  = (total_cs // 6_000) % 60
    h  =  total_cs // 360_000
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(boundaries: list, ass_path: str,
              out_w: int = 1080, out_h: int = 1920):
    """
    Write an ASS subtitle file from TTS sentence boundaries.
    Alignment 5 = middle-centre. Multi-line entries use ASS \\N hard line-breaks.
    """
    fontsize = 56
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {out_w}\n"
        f"PlayResY: {out_h}\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{FONT_NAME},{fontsize},"
        "&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "1,0,0,0,100,100,0,0,1,3,0,"
        "5,20,20,0,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text\n"
    )

    rows = []
    for i, b in enumerate(boundaries):
        start = _ass_time(b["offset"])
        if i + 1 < len(boundaries):
            end_offset = min(b["offset"] + b["duration"], boundaries[i + 1]["offset"])
        else:
            end_offset = b["offset"] + b["duration"]
        end   = _ass_time(end_offset)
        lines = _split_lines(b["text"])
        lines = [l.replace("{", "").replace("}", "") for l in lines]
        text  = r"\N".join(lines)
        rows.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8-sig") as f:
        f.write(header + "\n".join(rows))


def build_filter_script(ass_filename: str, script_path: str):
    """
    Write a one-filter filtergraph: ass subtitles only.
    Crop and scale are no longer needed because parkour.mp4 is already
    pre-rendered at 1080x1920.
    The ASS file is referenced by filename only so FFmpeg (run with cwd=tempdir)
    resolves it without any Windows drive-letter escaping in the filter string.
    """
    content = f"ass={ass_filename}:fontsdir=."
    with open(script_path, "w", encoding="ascii") as f:
        f.write(content)


def create_video(parkour_abs: str, audio_abs: str,
                 boundaries: list, output_abs: str):
    """Produce the final vertical 9:16 MP4 with burned-in captions."""
    tmp          = tempfile.gettempdir()
    job_id       = _job_id_from_path(audio_abs)
    ass_path     = os.path.join(tmp, f"_sub_{job_id}.ass")
    script_path  = os.path.join(tmp, f"_vf_{job_id}.txt")
    ass_filename = os.path.basename(ass_path)

    font_tmp = os.path.join(tmp, FONT_FILE)
    if not os.path.exists(font_tmp):
        shutil.copy2(FONT_PATH, font_tmp)

    duration = get_audio_duration(audio_abs)

    try:
        build_ass(boundaries, ass_path)
        build_filter_script(ass_filename, script_path)

        cmd = [
            _FFMPEG, "-y",
            "-stream_loop", "-1",
            "-i", parkour_abs,
            "-i", audio_abs,
            "-t", str(duration),
            "-filter_script:v", script_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_abs,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-3000:]}")
    finally:
        _cleanup(script_path, ass_path)


def _job_id_from_path(audio_path: str) -> str:
    base = os.path.basename(audio_path)   # _tts_<id>.mp3
    return base.replace("_tts_", "").replace(".mp3", "")


def _cleanup(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
