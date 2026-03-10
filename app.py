import os
import uuid
import time
import threading

from flask import Flask, request, jsonify, send_file, render_template

from services.reddit import fetch_reddit_post
from services.jobs import jobs, process_job, cleanup_old_jobs

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


MAX_TITLE_LEN = 300
MAX_STORY_LEN = 8_000  # ~1,500 words; keeps TTS + encoding time reasonable


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json(force=True)
    reddit_url = data.get("url", "").strip()
    if not reddit_url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        title, story = fetch_reddit_post(reddit_url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Could not fetch post. Check the URL and try again."}), 400
    if not story:
        return jsonify({"error": "No text body found. This might be a link/image post."}), 400
    return jsonify({"title": title, "story": story})


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    title = data.get("title", "").strip()[:MAX_TITLE_LEN]
    story = data.get("story", "").strip()[:MAX_STORY_LEN]
    if not title and not story:
        return jsonify({"error": "No content provided"}), 400

    cleanup_old_jobs()

    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {"status": "queued", "created_at": time.time()}

    threading.Thread(target=process_job, args=(job_id, title, story), daemon=True).start()

    return jsonify({"job_id": job_id})


@app.route("/api/video/<job_id>")
def serve_video(job_id):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Not found"}), 404
    path = job.get("video_path", "")
    if not os.path.exists(path):
        return jsonify({"error": "Video has expired"}), 410
    return send_file(path, mimetype="video/mp4", conditional=True)


@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
