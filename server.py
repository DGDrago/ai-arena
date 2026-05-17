#!/usr/bin/env python3
"""
AI Arena — Flask backend
Manages debate between Claude Code (file relay) and local LLM.
"""

import atexit
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR       = Path(__file__).resolve().parent
DEBATE_CHANNEL = BASE_DIR / "debate_channel.json"
WATCHER_SCRIPT = BASE_DIR / "watcher.py"
CONFIG_FILE    = BASE_DIR / "debate_config.json"
PYTHON_EXE     = Path(sys.executable)
FRONTEND_DIR   = BASE_DIR

# ---------------------------------------------------------------------------
# Known servers
# ---------------------------------------------------------------------------
KNOWN_SERVERS = [
    {
        "id": "ollama",   "name": "Ollama",         "port": 11434,
        "api_format":  "ollama",
        "check_url":   "http://localhost:11434/api/tags",
        "models_url":  "http://localhost:11434/api/tags",
        "chat_url":    "http://localhost:11434/api/chat",
    },
    {
        "id": "lmstudio", "name": "LM Studio",       "port": 1234,
        "api_format":  "openai",
        "check_url":   "http://localhost:1234/v1/models",
        "models_url":  "http://localhost:1234/v1/models",
        "chat_url":    "http://localhost:1234/v1/chat/completions",
    },
    {
        "id": "llamacpp", "name": "llama.cpp",        "port": 8080,
        "api_format":  "openai",
        "check_url":   "http://localhost:8080/v1/models",
        "models_url":  "http://localhost:8080/v1/models",
        "chat_url":    "http://localhost:8080/v1/chat/completions",
    },
    {
        "id": "jan",      "name": "Jan",              "port": 1337,
        "api_format":  "openai",
        "check_url":   "http://localhost:1337/v1/models",
        "models_url":  "http://localhost:1337/v1/models",
        "chat_url":    "http://localhost:1337/v1/chat/completions",
    },
    {
        "id": "textgen",  "name": "text-gen-webui",   "port": 5001,
        "api_format":  "openai",
        "check_url":   "http://localhost:5001/v1/models",
        "models_url":  "http://localhost:5001/v1/models",
        "chat_url":    "http://localhost:5001/v1/chat/completions",
    },
]
_SERVER_BY_ID = {s["id"]: s for s in KNOWN_SERVERS}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=str(FRONTEND_DIR))
CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*"])

_procs: list[subprocess.Popen] = []


def _kill_all():
    for p in _procs:
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    _procs.clear()


atexit.register(_kill_all)


def _spawn_silent(script: Path) -> subprocess.Popen:
    """Start a Python script with no visible window and no terminal output."""
    kwargs = dict(
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(BASE_DIR),
    )
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen([str(PYTHON_EXE), str(script)], **kwargs)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/api/servers")
def get_servers():
    result = []
    for s in KNOWN_SERVERS:
        try:
            r = requests.get(s["check_url"], timeout=2)
            available = r.status_code == 200
        except Exception:
            available = False
        result.append({
            "id": s["id"], "name": s["name"], "port": s["port"],
            "api_format": s["api_format"], "available": available,
        })
    return jsonify({"servers": result})


@app.route("/api/models")
def get_models():
    server = request.args.get("server", "ollama")
    srv = _SERVER_BY_ID.get(server)
    if not srv:
        return jsonify({"models": [], "error": f"Unknown server: {server}"}), 400
    try:
        r = requests.get(srv["models_url"], timeout=5)
        r.raise_for_status()
        if srv["api_format"] == "ollama":
            models = [m["name"] for m in r.json().get("models", [])]
        else:
            models = [m["id"] for m in r.json().get("data", [])]
        return jsonify({"models": models})
    except requests.exceptions.ConnectionError:
        return jsonify({"models": [], "error": f"Cannot connect to {server}"}), 200
    except Exception as e:
        return jsonify({"models": [], "error": str(e)}), 200


def _write_claude_context(config: dict):
    topics   = config.get("topics", [])
    model    = config.get("model", "?")
    server   = config.get("server", "ollama")
    url      = config.get("server_url", "")
    exchanges = int(config.get("exchanges_per_topic", 2))
    pushbacks = exchanges - 1

    topic_lines = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(topics))
    opening_hint = f'Open the debate with a strong thesis: {topics[0]}' if topics else ""

    text = f"""# Current Debate Session

**Opponent model:** {model}
**Server:** {server} — {url}
**Topics ({len(topics)}):**
{topic_lines}
**Push-backs per topic:** {pushbacks} (then verdict)
**Total exchanges per topic:** {exchanges}

## What to do right now

`debate_channel.json` is empty — you open the debate.

Your first prompt:
> "{opening_hint}"

After writing your opening, `watcher.py` will write the opponent's response automatically.
Watch `debate_channel.json` — when the last entry is `"role": "local"` it's your turn again.

After {pushbacks} counter(s), write a verdict (type: "verdict") that ends with:
WINNER: Claude  —or—  WINNER: {model}
"""
    (BASE_DIR / "_claude_context.md").write_text(text, encoding="utf-8")


@app.route("/api/start", methods=["POST"])
def start_debate():
    data            = request.get_json(force=True)
    server          = data.get("server", "ollama")
    model           = data.get("model", "gemma4:latest")
    topics          = data.get("topics", [])
    transcript_path = data.get("transcript_path", str(BASE_DIR / "transcript.md"))
    exchanges       = int(data.get("exchanges_per_topic", 2))
    claude_mode     = data.get("claude_mode", "manual")

    srv        = _SERVER_BY_ID.get(server)
    api_format = srv["api_format"] if srv else "ollama"
    server_url = srv["chat_url"]   if srv else data.get("server_url", "http://localhost:11434/api/chat")

    config = {
        "server": server, "server_url": server_url,
        "api_format": api_format,
        "model": model, "topics": topics,
        "transcript_path": transcript_path,
        "exchanges_per_topic": exchanges,
        "claude_mode": claude_mode,
    }
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    _kill_all()
    DEBATE_CHANNEL.write_text("[]", encoding="utf-8")

    _procs.append(_spawn_silent(BASE_DIR / "watcher.py"))
    if claude_mode == "auto":
        _procs.append(_spawn_silent(BASE_DIR / "claude_auto.py"))
    else:
        _write_claude_context(config)

    return jsonify({"status": "started", "claude_mode": claude_mode})


@app.route("/api/stop", methods=["POST"])
def stop_debate():
    _kill_all()
    return jsonify({"status": "stopped"})


@app.route("/api/stream")
def stream():
    def generate():
        last_count = 0
        last_ping  = time.time()

        while True:
            # Keepalive ping every 15 s
            if time.time() - last_ping >= 15:
                yield ": ping\n\n"
                last_ping = time.time()

            try:
                if not DEBATE_CHANNEL.exists():
                    time.sleep(0.5)
                    continue

                with open(DEBATE_CHANNEL, encoding="utf-8") as f:
                    messages = json.load(f)

                if len(messages) > last_count:
                    for i in range(last_count, len(messages)):
                        msg   = messages[i]
                        event = {
                            "role":         msg.get("role", "unknown"),
                            "content":      msg.get("content", ""),
                            "index":        i,
                            "round":        msg.get("round", 0),
                            "total_rounds": msg.get("total_rounds", 0),
                            "topic":        msg.get("topic", ""),
                            "type":         msg.get("type", "message"),
                        }
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    last_count = len(messages)

            except (json.JSONDecodeError, OSError):
                pass  # file mid-write, retry next tick

            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/save", methods=["POST"])
def save_transcript():
    data            = request.get_json(force=True)
    transcript_path = data.get("transcript_path", str(BASE_DIR / "ai_debate_transkript.md"))

    try:
        if not DEBATE_CHANNEL.exists():
            return jsonify({"status": "error", "error": "debate_channel.json not found"}), 404

        with open(DEBATE_CHANNEL, encoding="utf-8") as f:
            messages = json.load(f)

        lines = ["# AI Arena — Debate Transcript\n"]

        # Try to pull topic info from config
        if CONFIG_FILE.exists():
            try:
                cfg    = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                model  = cfg.get("model", "local LLM")
                topics = cfg.get("topics", [])
                lines.append(f"**Model:** {model}  \n")
                if topics:
                    lines.append(f"**Topics:** {', '.join(topics)}  \n")
            except Exception:
                pass

        lines.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M')}  \n\n---\n\n")

        for i, msg in enumerate(messages, 1):
            role    = msg.get("role", "unknown").upper()
            content = msg.get("content", "").strip()
            lines.append(f"### [{i}] {role}\n\n{content}\n\n---\n\n")

        out = Path(transcript_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(lines), encoding="utf-8")

        return jsonify({"status": "saved", "path": str(out)})

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/status")
def status():
    running = any(p.poll() is None for p in _procs)
    count   = 0
    if DEBATE_CHANNEL.exists():
        try:
            with open(DEBATE_CHANNEL, encoding="utf-8") as f:
                count = len(json.load(f))
        except Exception:
            pass
    return jsonify({"watcher_running": running, "message_count": count})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("AI Arena server — http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
