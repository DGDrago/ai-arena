#!/usr/bin/env python3
"""
claude_says.py — adds Claude's message to the debate channel.
Usage: python claude_says.py "your argument here"
"""

import json, sys
from pathlib import Path

DEBATE_FILE = Path(__file__).resolve().parent / "debate_channel.json"

if len(sys.argv) < 2:
    print('Usage: python claude_says.py "message"')
    sys.exit(1)

content = " ".join(sys.argv[1:])

try:
    messages = json.loads(DEBATE_FILE.read_text(encoding="utf-8"))
except Exception:
    messages = []

messages.append({"role": "claude", "content": content})
DEBATE_FILE.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] Added ({len(messages)} messages total)")
