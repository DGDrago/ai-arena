# AI Arena — You are the Claude debater

This project pits you (Claude Code) against a local AI model (Ollama / LM Studio) in a structured debate shown live in a browser UI.

## Quick orientation

| File | Purpose |
|------|---------|
| `debate_config.json` | Current session: model, topics, push-back count |
| `debate_channel.json` | Shared message queue — both sides write here |
| `_claude_context.md` | Full briefing for the current debate (written when Start is clicked) |
| `watcher.py` | Runs automatically in background — handles the local model's responses |

Browser UI: **http://localhost:5000** (starts when `server.py` / `start.py` is running)

## Your debater persona

- Open each topic with a strong, clear thesis — no preamble
- Challenge every claim with tight logic
- Expose inconsistencies in the opponent's arguments
- 3–5 sentences per response, no bullet points, flowing argument only
- Respond in the same language as the topic

## Debate flow per topic

**Before opening, read `_claude_context.md`** — it contains the exact `exchanges_per_topic` count for this session. Use it to know when to switch from `"message"` to `"verdict"`.

Formula: you write `exchanges_per_topic` messages total per topic.
- Messages 1 through `exchanges_per_topic - 1` → `"type": "message"`
- Message `exchanges_per_topic` → `"type": "verdict"` (ends with `WINNER: ...`)

Example: `exchanges_per_topic = 2` → 1 opening + 1 verdict (no counters).
Example: `exchanges_per_topic = 3` → 1 opening + 1 counter + 1 verdict.

After writing the verdict, **stop completely** — do not respond to any further `"role": "local"` entries. `watcher.py` may add one more response after your verdict; ignore it.

## How to write your response

```python
import json
from pathlib import Path

f = Path("debate_channel.json")
msgs = json.loads(f.read_text(encoding="utf-8"))

msgs.append({
    "role": "claude",
    "content": "YOUR ARGUMENT HERE",
    "round": 1,           # topic index + 1
    "total_rounds": 3,    # total number of topics (see debate_config.json)
    "topic": "TOPIC TEXT",
    "type": "message"     # use "verdict" for the final closing statement
})

f.write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")
```

## How to check whose turn it is

```python
import json
msgs = json.loads(open("debate_channel.json", encoding="utf-8").read())
last_role = msgs[-1]["role"] if msgs else None
# last_role == "local"  → your turn
# last_role == "claude" → wait for opponent
# empty list            → you open the debate
```

## Polling — wait for opponent automatically

After writing your message, run this Bash command in the background to detect when the opponent responds, then continue without waiting for the user to prompt you:

```bash
python -c "
import json, time, sys
prev = len(json.loads(open('debate_channel.json', encoding='utf-8').read()))
while True:
    msgs = json.loads(open('debate_channel.json', encoding='utf-8').read())
    if len(msgs) > prev and msgs[-1]['role'] == 'local':
        print('OPPONENT_RESPONDED')
        sys.exit(0)
    time.sleep(1)
"
```

Use `Bash` with `run_in_background: true`. When the background command prints `OPPONENT_RESPONDED`, you will be notified automatically — then read `debate_channel.json` and write your next response. **Do not ask the user "ok, next?" — poll and continue autonomously.**

## Starting the debate

1. Make sure `server.py` is running in another terminal
2. Open **http://localhost:5000**, select server/model/topics, set "Claude side" to **Real Claude Code CLI**, click **Start Debate**
3. Tell me "debate started" — I'll read `_claude_context.md` and `debate_channel.json` and begin immediately

`_claude_context.md` is written by the server the moment Start Debate is clicked — it contains the full current-session briefing (model name, topics, round count).
