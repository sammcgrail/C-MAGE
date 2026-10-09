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
# exit 2 = bad arguments, 3 = launcher failed, 4 = reader served by the wrong model, prompt altered,
#          or the reader delegated images to sub-agents
set -uo pipefail
MODEL="${1:-}"; PROMPT="${2:-}"; TYPE="${3:-general-purpose-max}"
case "$MODEL" in
  claude-sonnet-*) ;;
  *) echo "model must be an explicit claude-sonnet-* id, not an alias: '$MODEL'" >&2; exit 2 ;;
esac
[ -s "$PROMPT" ] || { echo "no prompt file at '$PROMPT'" >&2; exit 2; }
PY=/root/C-MAGE/.venv-ms/bin/python
HERE=$(cd "$(dirname "$0")" && pwd)
CLAUDE=/root/.local/bin/claude

WD=$(mktemp -d /tmp/reader-launch.XXXXXX) || exit 3
# Named on stderr first, so a caller can find the launcher's transcripts (e.g. to tell a rate limit
# from any other failure) even when this script exits before the reader is identified.
echo "LAUNCH_DIR $WD" >&2
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

# THE LOCKDOWN (29 Sep). Three Sonnet 5.5 readers ran `ls /root/C-MAGE` hunting for other OCSR
# tools and got the repo listing; the gate refused them, but a prompt rule is only a request. So the
# launcher and its reader run inside tools/reader_sandbox.sh: a bubblewrap mount namespace where
# /root/C-MAGE holds nothing but .venv-ms (read-only, same path), the rest of /root, other sessions'
# transcripts and the host /tmp are masked, and the reader sees a private /tmp holding only the
# launch dir and its blind images. The toolset is unchanged: the same Read/Write/Edit/Bash/Glob/Grep,
# the same interpreter with RDKit, the same system binaries (osra). On top, permission deny rules
# (reader_settings.json) refuse Read/Glob/Grep on the answer paths and the obvious Bash listings,
# so a reader that tries is told "denied" at once instead of seeing an empty directory.
# Since 8 Oct the jail also has no network but the model API (tools/jail_proxy.py, allowlist) and no
# name-to-structure tools; every request it made is in $WD/jail_net.jsonl, checked below.
# Selftest: tools/test_reader_sandbox.sh.
PRIV=$(mktemp -d /tmp/reader-tmp.XXXXXX) || exit 3
cp "$HERE/reader_settings.json" "$WD/reader_settings.json" || exit 3
( cd "$WD" && env -u CLAUDE_CODE_SUBAGENT_MODEL -u CLAUDE_CODE_EFFORT_LEVEL \
    ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL" \
    "$HERE/reader_sandbox.sh" "$WD" "$PRIV" "$WD/reader_prompt.txt" -- \
    "$CLAUDE" -p "$(cat "$WD/launch.txt")" --model "$MODEL" --effort low \
      --settings "$WD/reader_settings.json" \
      --allowedTools "Read,Write,Edit,Bash,Glob,Grep,Agent,Task" \
      --output-format stream-json --verbose < /dev/null > "$WD/out.jsonl" 2> "$WD/err.txt" ) \
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
if len(hits) > 1:
    # The reader itself called the Agent tool: its images were (partly) read by sub-agents on
    # whatever model THEIR type pins. Seen 28 Sep: a claude-sonnet-5 reader handed 7 of 10 images
    # to general-purpose-high sub-agents served by claude-opus-5-5. Not that model's reading.
    for h in sorted(hits):
        ms = sorted({(json.loads(l).get("message") or {}).get("model") or "" for l in open(h)
                     if l.strip() and json.loads(l).get("type") == "assistant"} - {"", "<synthetic>"})
        print(f"  {h.rsplit('agent-', 1)[1][:-6]}: {ms}", file=sys.stderr)
    print(f"REFUSE: {len(hits)} transcripts under session {session}: the reader delegated to "
          f"{len(hits) - 1} sub-agent(s), so this is not a {model} reading", file=sys.stderr)
    sys.exit(4)
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
# The jail's network log must exist (proof the reader ran behind the proxy, in its own network
# namespace); denied requests are reported, not refused here: the gate's scan decides what they mean.
import os
netlog = f"{wd}/jail_net.jsonl"
if not os.path.exists(netlog):
    print(f"REFUSE: no {netlog}: the reader did not run behind the jail's network proxy", file=sys.stderr)
    sys.exit(3)
net = [json.loads(l) for l in open(netlog) if l.strip()]
denied = sorted({n["target"] for n in net if not n.get("allowed")} - {"CONNECT mcp-proxy.anthropic.com:443 HTTP/1.1"})
if denied:
    print(f"NOTE: the jail refused {len(denied)} target(s): {denied[:5]}", file=sys.stderr)
print(f"READER {real_aid} {model}")
PYEOF
