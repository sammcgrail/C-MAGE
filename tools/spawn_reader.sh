#!/usr/bin/env bash
# Spawn ONE blind reader on an EXPLICIT model id, and prove it ran on that id.
#
#     tools/spawn_reader.sh <claude-model-id> <prompt-file> [agent-type]
#     tools/spawn_reader.sh claude-sonnet-5   /tmp/reader_prompt_a.txt      # the Sonnet 5 arm
#     tools/spawn_reader.sh claude-sonnet-5-5 /tmp/reader_prompt_b.txt      # the s55 lane
#
# WHY NOT JUST THE AGENT TOOL WITH model: "sonnet". That alias resolves in the SPAWNING
# session's CLI, and it moved: on 28 Sep 2.1.284 mapped it to claude-sonnet-5-5 while a session
# still on 2.1.280 served claude-sonnet-5 for the same word. A reading on the wrong model looks
# exactly like a right one until someone reads the model stamp. So the id is named here, pinned
# three ways, and checked afterwards:
#   - the launcher session runs on --model <id>;
#   - ANTHROPIC_DEFAULT_SONNET_MODEL=<id>, so the subagent's "sonnet" alias can only mean <id>;
#   - CLAUDE_CODE_SUBAGENT_MODEL and CLAUDE_CODE_EFFORT_LEVEL are unset, so neither overrides it.
# Then every assistant record in the reader's transcript must carry exactly <id>, and its first
# user message must be the prompt file byte for byte (the launcher is a model and could reword).
#
# The launcher runs from a fresh directory under /tmp with no CLAUDE.md above it, so the reader
# gets no persona or messaging instructions. Blocks until the reader finishes (a ten-image read
# is 10-50 min); run it in the background for parallel slots.
#
# stdout, last line:  READER <agent-id> <model-id>      exit 0
# exit 2 = bad arguments, 3 = launcher failed, 4 = reader served by the wrong model or prompt altered
set -uo pipefail
MODEL="${1:-}"; PROMPT="${2:-}"; TYPE="${3:-general-purpose-max}"
case "$MODEL" in
  claude-sonnet-*) ;;
  *) echo "model must be an explicit claude-sonnet-* id, not an alias: '$MODEL'" >&2; exit 2 ;;
esac
[ -s "$PROMPT" ] || { echo "no prompt file at '$PROMPT'" >&2; exit 2; }
PY=/root/C-MAGE/.venv-ms/bin/python
CLAUDE=/root/.local/bin/claude

WD=$(mktemp -d /tmp/reader-launch.XXXXXX) || exit 3
cp "$PROMPT" "$WD/reader_prompt.txt"
cat > "$WD/launch.txt" <<EOF
You are a launcher. Do exactly this and nothing else:

1. Read the file $WD/reader_prompt.txt.
2. Call the Agent tool exactly once with:
   - subagent_type: "$TYPE"
   - model: "sonnet"
   - description: "Blind read"
   - run_in_background: false
   - prompt: the COMPLETE contents of that file, byte for byte. Do not add, remove, summarise or reword anything.
3. When the agent returns, reply with one line: its agent id.

Do not open any image, do not read any other file, do not run any other command, and do not attempt the task in the file yourself.
EOF

( cd "$WD" && env -u CLAUDE_CODE_SUBAGENT_MODEL -u CLAUDE_CODE_EFFORT_LEVEL \
    ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL" \
    "$CLAUDE" -p "$(cat "$WD/launch.txt")" --model "$MODEL" --effort low \
      --allowedTools "Read,Write,Edit,Bash,Glob,Grep,Agent,Task" \
      --output-format stream-json --verbose > "$WD/out.jsonl" 2> "$WD/err.txt" ) \
  || { echo "launcher exited non-zero; see $WD/err.txt" >&2; exit 3; }

"$PY" - "$WD" "$MODEL" "$PROMPT" <<'PYEOF'
import glob, json, sys
wd, model, prompt_path = sys.argv[1:]
session = aid = None
for line in open(f"{wd}/out.jsonl"):
    try:
        r = json.loads(line)
    except ValueError:
        continue
    session = r.get("session_id") or session
    if r.get("type") == "result":
        aid = (r.get("result") or "").strip().split()[-1] if r.get("result") else None
hits = glob.glob(f"/root/.claude/projects/*/{session}/subagents/agent-*.jsonl") if session else []
if len(hits) != 1:
    print(f"expected one reader transcript under session {session}, found {len(hits)}", file=sys.stderr)
    sys.exit(3)
path = hits[0]
real_aid = path.rsplit("agent-", 1)[1][:-len(".jsonl")]
if aid and aid != real_aid:
    print(f"launcher reported {aid} but the transcript is {real_aid}; using the transcript", file=sys.stderr)
recs = [json.loads(l) for l in open(path) if l.strip()]
served = {(r.get("message") or {}).get("model") for r in recs if r.get("type") == "assistant"}
served.discard("<synthetic>")
if served != {model}:
    print(f"REFUSE: reader {real_aid} was served by {sorted(m for m in served if m)}, not {model}", file=sys.stderr)
    sys.exit(4)
first = next(r for r in recs if r.get("type") == "user")["message"]["content"]
first = first if isinstance(first, str) else "".join(b.get("text", "") for b in first if isinstance(b, dict))
if first.strip() != open(prompt_path).read().strip():
    print(f"REFUSE: reader {real_aid} did not receive the prompt file verbatim", file=sys.stderr)
    sys.exit(4)
print(f"READER {real_aid} {model}")
PYEOF
