#!/usr/bin/env python3
"""
claude_auto.py — drives Claude's side of the debate using a local model with adversarial persona.
Run this after starting the debate from the UI (watcher.py handles the opponent's side).

Usage: python claude_auto.py
Config is read from debate_config.json (written by server.py on Start).

Optional keys in debate_config.json:
  "claude_model"         — which model plays Claude (default: same as opponent)
  "exchanges_per_topic"  — back-and-forth rounds per topic (default: 2)
  "language"             — debate language hint for the system prompt (default: "English")
"""

import json, sys, time, requests
from pathlib import Path

HERE        = Path(__file__).resolve().parent
DEBATE_FILE = HERE / "debate_channel.json"
CONFIG_FILE = HERE / "debate_config.json"

BOLD  = "\033[1m"
CYAN  = "\033[96m"
DIM   = "\033[2m"
RESET = "\033[0m"

CLAUDE_SYSTEM = (
    "You are Claude, a sharp and precise AI debater. Rules:\n"
    "- Open with a strong, clear thesis — no preamble\n"
    "- Challenge every claim with tight logic\n"
    "- Expose inconsistencies in the opponent's arguments\n"
    "- Be direct and intellectually rigorous, 3-5 sentences max\n"
    "- No bullet points, flowing argument only\n"
    "- Respond in the same language as the topic"
)


def load_config():
    if not CONFIG_FILE.exists():
        print("[ERROR] debate_config.json not found. Start a debate from the UI first.")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def read_channel():
    try:
        return json.loads(DEBATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def write_channel(messages):
    DEBATE_FILE.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_messages(history, opening_prompt=None):
    msgs = [{"role": "system", "content": CLAUDE_SYSTEM}]
    if opening_prompt:
        msgs.append({"role": "user", "content": opening_prompt})
        return msgs
    for m in history:
        if m["role"] == "claude":
            msgs.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "local":
            msgs.append({"role": "user", "content": m["content"]})
    return msgs


def call_model(server_url, model, history, opening_prompt=None, server="ollama"):
    msgs = build_messages(history, opening_prompt)
    resp = requests.post(
        server_url,
        json={"model": model, "messages": msgs, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    if server == "openai":
        return data["choices"][0]["message"]["content"].strip()
    return data["message"]["content"].strip()


def wait_for_opponent(min_count):
    """Blocks until debate_channel has >= min_count messages and last is from 'local'."""
    while True:
        msgs = read_channel()
        if len(msgs) >= min_count and msgs[-1]["role"] == "local":
            return msgs
        time.sleep(0.5)


def main():
    cfg             = load_config()
    api_format      = cfg.get("api_format", "ollama")
    server_url      = cfg.get("server_url", "http://localhost:11434/api/chat")
    claude_model    = cfg.get("claude_model") or cfg.get("model", "gemma4:latest")
    topics          = cfg.get("topics", ["Is AI creativity genuine?"])
    exchanges       = int(cfg.get("exchanges_per_topic", 2))

    print(f"\n{BOLD}{'═' * 58}{RESET}")
    print(f"{BOLD}  Claude Auto  ·  model: {claude_model}{RESET}")
    print(f"{BOLD}  {len(topics)} topic(s) · {exchanges} exchange(s) each{RESET}")
    print(f"{BOLD}{'═' * 58}{RESET}\n")

    total = len(topics)

    def send_claude(text, t_idx, msg_type="message"):
        fresh = read_channel()
        fresh.append({"role": "claude", "content": text,
                      "round": t_idx + 1, "total_rounds": total, "topic": topics[t_idx],
                      "type": msg_type})
        write_channel(fresh)
        print(f"{BOLD}{CYAN}[CLAUDE]{RESET} {text[:120]}\n")

    def wait_and_get():
        count = len(read_channel())
        msgs  = wait_for_opponent(count + 1)
        time.sleep(1.0)
        return msgs

    def generate(history, prompt=None):
        try:
            return call_model(server_url, claude_model, history, opening_prompt=prompt, server=api_format)
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    for t_idx, topic in enumerate(topics):
        print(f"{DIM}── Topic {t_idx + 1}/{len(topics)}: {topic} ──{RESET}")

        # 1. Claude otvara
        send_claude(generate(read_channel(),
                             prompt=f"Open the debate with a strong thesis: {topic}"),
                    t_idx)

        # 2. exchanges - 1 puta: čekaj protivnika, Claude kontra
        for _ in range(exchanges - 1):
            msgs = wait_and_get()
            send_claude(generate(msgs), t_idx)

        # 3. Čekaj zadnji protivnikov odgovor, Claude daje verdikt
        msgs = wait_and_get()
        verdict_prompt = (
            "Give a 2-3 sentence closing verdict for this debate topic. "
            "Identify the strongest point each side made, then declare a clear winner: "
            "either 'WINNER: Claude' or 'WINNER: [opponent name]' — be honest, "
            "the opponent wins if their arguments were objectively stronger."
        )
        send_claude(generate(msgs, prompt=verdict_prompt), t_idx, msg_type="verdict")

    print(f"\n{BOLD}Debate complete.{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{DIM}Stopped.{RESET}\n")
