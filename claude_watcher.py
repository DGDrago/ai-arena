#!/usr/bin/env python3
"""
claude_watcher.py — drives Claude's side using the Anthropic API.
Requires ANTHROPIC_API_KEY in environment or .env file.

Optional debate_config.json keys:
  "claude_api_model" — which Claude model to use (default: claude-sonnet-4-6)
"""

import json, os, sys, time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("[ERROR] anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HERE        = Path(__file__).resolve().parent
DEBATE_FILE = HERE / "debate_channel.json"
CONFIG_FILE = HERE / "debate_config.json"

BOLD  = "\033[1m"
CYAN  = "\033[96m"
DIM   = "\033[2m"
RESET = "\033[0m"

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM = (
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
    DEBATE_FILE.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")


def build_messages(history, opening_prompt=None):
    if opening_prompt:
        return [{"role": "user", "content": opening_prompt}]
    msgs = []
    for m in history:
        if m["role"] == "claude":
            msgs.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "local":
            msgs.append({"role": "user", "content": m["content"]})
    # Anthropic requires messages to start with user role
    if msgs and msgs[0]["role"] == "assistant":
        msgs.insert(0, {"role": "user", "content": "Begin the debate."})
    return msgs


def call_claude(client, model, history, opening_prompt=None):
    msgs = build_messages(history, opening_prompt)
    if not msgs:
        msgs = [{"role": "user", "content": "Begin the debate."}]
    response = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM,
        messages=msgs,
    )
    return response.content[0].text.strip()


def wait_for_opponent(min_count):
    while True:
        msgs = read_channel()
        if len(msgs) >= min_count and msgs[-1]["role"] == "local":
            return msgs
        time.sleep(1.0)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not set. Add it to .env or set the environment variable.")
        sys.exit(1)

    cfg       = load_config()
    model     = cfg.get("claude_api_model", DEFAULT_MODEL)
    topics    = cfg.get("topics", ["Is AI creativity genuine?"])
    exchanges = int(cfg.get("exchanges_per_topic", 2))
    total     = len(topics)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{BOLD}{'═' * 58}{RESET}")
    print(f"{BOLD}  Claude API Watcher  ·  {model}{RESET}")
    print(f"{BOLD}  {total} topic(s) · {exchanges} exchange(s) each{RESET}")
    print(f"{BOLD}{'═' * 58}{RESET}\n")

    def send_claude(text, t_idx, msg_type="message"):
        fresh = read_channel()
        fresh.append({
            "role": "claude", "content": text,
            "round": t_idx + 1, "total_rounds": total,
            "topic": topics[t_idx], "type": msg_type,
        })
        write_channel(fresh)
        print(f"{BOLD}{CYAN}[CLAUDE]{RESET} {text[:120]}\n")

    def wait_and_get():
        count = len(read_channel())
        msgs  = wait_for_opponent(count + 1)
        time.sleep(0.5)
        return msgs

    for t_idx, topic in enumerate(topics):
        print(f"{DIM}── Topic {t_idx + 1}/{total}: {topic} ──{RESET}")

        send_claude(
            call_claude(client, model, read_channel(),
                        opening_prompt=f"Open the debate with a strong thesis: {topic}"),
            t_idx,
        )

        for _ in range(exchanges - 1):
            msgs = wait_and_get()
            send_claude(call_claude(client, model, msgs), t_idx)

        msgs = wait_and_get()
        send_claude(
            call_claude(client, model, msgs, opening_prompt=(
                "Give a 2-3 sentence closing verdict. Identify the strongest point each side made, "
                "then declare a winner: either 'WINNER: Claude' or 'WINNER: [opponent name]' — be honest."
            )),
            t_idx, msg_type="verdict",
        )

    print(f"\n{BOLD}Debate complete.{RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{DIM}Stopped.{RESET}\n")
