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

1. **Open** — write your first message (thesis)
2. Wait for `watcher.py` to write the opponent's response (`role: "local"`)
3. **Counter** — repeat `exchanges_per_topic - 1` times
4. **Verdict** — after the opponent's last response, declare a winner honestly:
   end with `WINNER: Claude` or `WINNER: [model name]`

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

## Starting the debate

1. Make sure `server.py` is running in another terminal
2. Open **http://localhost:5000**, select server/model/topics, set "Claude side" to **Real Claude Code CLI**, click **Start Debate**
3. Tell me "debate started" — I'll read `_claude_context.md` and `debate_channel.json` and begin immediately

`_claude_context.md` is written by the server the moment Start Debate is clicked — it contains the full current-session briefing (model name, topics, round count).
