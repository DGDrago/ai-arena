#!/usr/bin/env python3
"""
watcher.py — prati debate_channel.json, poziva lokalni LLM via Ollama/LM Studio.
Pokreni u novom terminalu: python watcher.py
"""

import json, time, requests, sys
from pathlib import Path

HERE        = Path(__file__).resolve().parent
DEBATE_FILE = HERE / "debate_channel.json"
CONFIG_FILE = HERE / "debate_config.json"

_DEFAULT_URL   = "http://localhost:11434/api/chat"
_DEFAULT_MODEL = "gemma4:latest"

def _load_config():
    if CONFIG_FILE.exists():
        try:
            cfg   = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return cfg.get("server_url", _DEFAULT_URL), cfg.get("model", _DEFAULT_MODEL)
        except Exception:
            pass
    return _DEFAULT_URL, _DEFAULT_MODEL

OLLAMA_URL, MODEL = _load_config()

SYSTEM = (
    "You are participating in a debate with another AI (Claude). "
    "Reply in the same language as the user's topics. "
    "Be direct, defend your position firmly but logically. "
    "3-5 sentences per reply, no bullet lists, plain text only."
)

CYAN  = "\033[96m"
YEL   = "\033[93m"
BOLD  = "\033[1m"
DIM   = "\033[2m"
RESET = "\033[0m"

def read_channel():
    try:
        return json.loads(DEBATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def write_channel(messages):
    DEBATE_FILE.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def build_messages(history):
    msgs = [{"role": "system", "content": SYSTEM}]
    for m in history:
        msgs.append({
            "role": "user" if m["role"] == "claude" else "assistant",
            "content": m["content"],
        })
    return msgs

def _get_api_format():
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return cfg.get("api_format", "ollama")
    except Exception:
        return "ollama"

def call_local(history):
    api_format = _get_api_format()
    full = ""
    try:
        if api_format == "openai":
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "messages": build_messages(history), "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            full = resp.json()["choices"][0]["message"]["content"].strip()
        else:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "messages": build_messages(history), "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full += token
                if chunk.get("done"):
                    break
    except Exception as e:
        print(f"\n{BOLD}[ERROR]{RESET} {e}")
    return full

def main():
    if not DEBATE_FILE.exists():
        write_channel([])

    print(f"\n{BOLD}{'═' * 58}{RESET}")
    print(f"{BOLD}  AI ARENA  ·  Claude  vs.  {MODEL}{RESET}")
    print(f"{BOLD}{'═' * 58}{RESET}\n")
    print(f"{DIM}Waiting for Claude's first message...{RESET}\n")

    processed = 0
    while True:
        messages = read_channel()
        if len(messages) <= processed:
            time.sleep(0.4)
            continue

        msg = messages[processed]
        if msg["role"] == "claude":
            print(f"{BOLD}{CYAN}[CLAUDE]{RESET} {msg['content']}")
            response = call_local(messages[:processed + 1])
            fresh = read_channel()
            fresh.append({"role": "local", "content": response})
            write_channel(fresh)
            processed += 2
        elif msg["role"] == "local":
            processed += 1
        time.sleep(0.4)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{DIM}Debate ended.{RESET}\n")
