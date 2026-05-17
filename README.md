# AI Arena — Debate Engine

Watch **Claude Code** debate a local LLM (Ollama / LM Studio / llama.cpp / Jan / text-gen-webui) on any topic, live in the browser.

```
Claude Code CLI  ─┐
                   ├──  debate_channel.json  ──  watcher.py  ──  local LLM
Auto mode      ──┘                                   │
                                                  server.py
                                                     │
                                                 browser UI (SSE)
```

Two modes:
- **Real Claude Code CLI** — you run `claude` in one terminal; it reads `CLAUDE.md`, gets the full briefing automatically, and participates as the Claude side
- **Auto (local model)** — `claude_auto.py` plays Claude's role using the same local server with an adversarial persona; fully autonomous, no CLI needed

---

## Quick start

### Requirements
- Python 3.10+
- [Ollama](https://ollama.com) **or** [LM Studio](https://lmstudio.ai) running with a model loaded
- [Claude Code CLI](https://docs.anthropic.com/claude-code) — only for Real Claude mode

### Install
```bash
git clone https://github.com/DGDrago/ai-arena
cd ai-arena
pip install -r requirements.txt
```

### Run
```bash
python start.py
```
Browser opens at **http://localhost:5000** automatically.

---

## Usage

1. **Browser** — configure server, model, topics, push-back count, Claude side
2. Click **Start Debate**
3. If using **Real Claude Code CLI** mode:
   - Open a second terminal: `cd ai-arena && claude`
   - Claude reads `CLAUDE.md` automatically — full briefing is there
   - Tell it: `debate started` — it reads `_claude_context.md` and begins
4. Watch the debate in the browser, save transcript when done

---

## Supported servers

| Server | Port | Notes |
|--------|------|-------|
| [Ollama](https://ollama.com) | 11434 | `ollama pull gemma4` |
| [LM Studio](https://lmstudio.ai) | 1234 | Enable Local Server in LM Studio |
| [llama.cpp](https://github.com/ggerganov/llama.cpp) | 8080 | `llama-server -m model.gguf` |
| [Jan](https://jan.ai) | 1337 | Enable Local API Server in Jan settings |
| [text-generation-webui](https://github.com/oobabooga/text-generation-webui) | 5001 | Enable `--api` flag |

Servers not currently running are shown grayed out in the UI — click the ↺ button to re-check.

---

## File structure

```
ai-arena/
├── server.py              # Flask backend — coordinates the debate
├── index.html             # Web UI (single-page app, SSE stream)
├── watcher.py             # Polls channel, calls local LLM for opponent responses
├── claude_auto.py         # Auto mode: drives Claude's side with local model
├── start.py               # Launcher: starts server + opens browser
├── CLAUDE.md              # Auto-loaded by Claude Code — full debater briefing
├── requirements.txt
│
├── debate_channel.json    # Runtime: shared message queue          [generated]
├── debate_config.json     # Runtime: current session config        [generated]
└── _claude_context.md     # Runtime: per-session briefing for CLI  [generated]
```

---

## How it works

`debate_channel.json` is the shared message queue:
```json
[
  {"role": "claude",  "content": "...", "round": 1, "total_rounds": 2, "topic": "...", "type": "message"},
  {"role": "local",   "content": "...", "round": 1, "total_rounds": 2, "topic": "..."},
  {"role": "claude",  "content": "...", "type": "verdict"}
]
```

- **`watcher.py`** polls the file every 0.4s; when it sees a new Claude message it calls the local model and appends the response
- **`server.py`** SSE endpoint streams new entries to the browser as they appear
- **`claude_auto.py`** (auto mode) calls the same local model with a Claude adversarial system prompt

---

## License

GNU
