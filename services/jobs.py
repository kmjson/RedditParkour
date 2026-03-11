import os
import tempfile
import threading
import time

from services.tts import generate_tts, expand_for_tts, restore_acronyms_in_subtitles
from services.video import create_video, _cleanup

PROJECT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_MAX_AGE = 30 * 60  # seconds before a completed video is eligible for cleanup

# Shared in-memory job store
jobs: dict = {}


def process_job(job_id: str, title: str, story: str):
    jobs[job_id].update({"title": title, "story": story, "status": "generating_tts"})

    tmp          = tempfile.gettempdir()
    audio_path   = os.path.join(tmp, f"_tts_{job_id}.mp3")
    output_path  = os.path.join(tmp, f"video_{job_id}.mp4")
    parkour_path = os.path.join(PROJECT_DIR, "static", "assets", "cs.mp4")

    try:
        full_text  = expand_for_tts(f"{title}. {story}")
        boundaries = generate_tts(full_text, audio_path)
        restore_acronyms_in_subtitles(boundaries)
    except Exception:
        jobs[job_id] = {"status": "error", "error": "Speech generation failed. Please try again."}
        _cleanup(audio_path)
        return

    jobs[job_id]["status"] = "creating_video"

    try:
        create_video(parkour_path, audio_path, boundaries, output_path)
    except Exception:
        jobs[job_id] = {"status": "error", "error": "Video encoding failed. Please try again."}
        _cleanup(audio_path)
        return

    _cleanup(audio_path)
    jobs[job_id]["status"]     = "done"
    jobs[job_id]["video_path"] = output_path
    jobs[job_id]["video_url"]  = f"/api/video/{job_id}"


def cleanup_old_jobs():
    """Remove video files and job entries older than VIDEO_MAX_AGE seconds."""
    cutoff = time.time() - VIDEO_MAX_AGE
    for jid in list(jobs):
        job = jobs.get(jid, {})
        if job.get("created_at", 0) < cutoff:
            _cleanup(job.get("video_path"))
            jobs.pop(jid, None)
