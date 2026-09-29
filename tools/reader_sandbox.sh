#!/usr/bin/env bash
# Run a command (the blind reader's launcher) inside a filesystem jail that cannot see the answer key.
#
#     tools/reader_sandbox.sh <launch-dir> <private-tmp> <prompt-file> -- <command> [args...]
#
# WHY. On 29 Sep three Sonnet 5.5 corpus readers (batches 9, 11, 17) ran `ls /root/C-MAGE` while
# looking for other OCSR tools, and got the repo listing: benchmarks/, results/, the other models.
# The gate refused all three, correctly, but a prompt rule is only a request. This makes the
# answer key NOT THERE for the reader, whatever it runs:
#   - a private mount namespace (bubblewrap) over the real filesystem, with every entry in /root
#     masked by an empty tmpfs (or /dev/null for a file) except what the CLI and its hooks need:
#     .claude .claude.json* .local .cargo .parry .parry-guard seb .bashrc .profile;
#   - /root/C-MAGE is an empty tmpfs with ONLY .venv-ms bound back, read-only, at the same path,
#     so the method's interpreter (Python + RDKit, the path the prompt names) is unchanged;
#   - inside ~/.claude: projects/ is masked and only THIS launcher's project dir is bound back (the
#     reader's transcript must still land where the gate looks); file-history, paste-cache,
#     backups, downloads, debug and history.jsonl are masked;
#   - inside /root/seb: transcripts, data, attachments, signal-data, backups, tmp, temp, notes;
#   - /tmp is a private directory: only the launch dir and the blind image dirs named in the
#     prompt (read-only) are in it, so other readers' answers and scratch, the corpus copies
#     under /tmp and other sessions' task outputs are gone;
#   - /home, /var/lib/docker, /var/lib/containerd masked; the docker socket is /dev/null;
#   - its own PID namespace and /proc (so /proc/1/root cannot reach the host's view), a minimal
#     /dev (no block devices), and --cap-drop ALL, so uid 0 inside cannot umount or remount the
#     masks away.
# Network stays: the CLI needs the API and the reader rule allows package installs; network
# lookups are still the transcript scanner's job.
#
# The answers file is written inside the private /tmp; after the command exits, every
# /tmp/<name>.json the prompt names is copied out (cp -p, so its mtime is the reader's write).
set -uo pipefail
WD="${1:-}"; PRIV="${2:-}"; PROMPT="${3:-}"
[ "${4:-}" = "--" ] || { echo "usage: reader_sandbox.sh <launch-dir> <private-tmp> <prompt-file> -- cmd..." >&2; exit 2; }
shift 4
[ -d "$WD" ] && [ -d "$PRIV" ] && [ -s "$PROMPT" ] || { echo "reader_sandbox: bad dirs/prompt" >&2; exit 2; }
command -v bwrap >/dev/null || { echo "reader_sandbox: bwrap missing (apt-get install bubblewrap)" >&2; exit 3; }

VENV=/root/C-MAGE/.venv-ms
PROJ=/root/.claude/projects/$(printf '%s' "$WD" | sed 's#[^A-Za-z0-9]#-#g')
mkdir -p "$PROJ"

BW=(bwrap --die-with-parent --unshare-pid --unshare-ipc --cap-drop ALL
    --bind / / --dev /dev --proc /proc)

# A symlink directly in /root could point anywhere; there are none today. Refuse rather than guess.
if find /root -maxdepth 1 -type l | grep -q .; then
  echo "reader_sandbox: symlink(s) in /root, mask them explicitly: $(find /root -maxdepth 1 -type l | tr '\n' ' ')" >&2
  exit 3
fi
KEEP_DIRS=" .claude .local .cargo .parry .parry-guard seb "
for p in /root/* /root/.[!.]*; do
  [ -e "$p" ] || continue
  n=${p##*/}
  if [ -d "$p" ]; then
    case "$KEEP_DIRS" in *" $n "*) continue ;; esac
    BW+=(--tmpfs "$p")
  else
    case "$n" in .claude.json*|.bashrc|.profile) continue ;; esac
    BW+=(--ro-bind /dev/null "$p")
  fi
done
# the repo: empty, except the method's interpreter, read-only, at the path the prompt names
BW+=(--ro-bind "$VENV" "$VENV")
# ~/.claude: other sessions' transcripts, file backups and prompt history
BW+=(--tmpfs /root/.claude/projects --bind "$PROJ" "$PROJ")
for d in file-history paste-cache backups downloads debug; do
  [ -d "/root/.claude/$d" ] && BW+=(--tmpfs "/root/.claude/$d")
done
[ -e /root/.claude/history.jsonl ] && BW+=(--bind /dev/null /root/.claude/history.jsonl)
# /root/seb stays for the CLI's hooks (they import the seb package); its conversation data does not
for d in transcripts data discord-attachments signal-data backups tmp temp notes; do
  [ -d "/root/seb/$d" ] && BW+=(--tmpfs "/root/seb/$d")
done
for d in /home /var/lib/docker /var/lib/containerd; do
  [ -d "$d" ] && BW+=(--tmpfs "$d")
done
for s in /run/docker.sock /run/containerd/containerd.sock; do
  [ -e "$s" ] && BW+=(--ro-bind /dev/null "$s")
done
# private /tmp: the launch dir, and the blind image dirs the prompt names (read-only)
BW+=(--bind "$PRIV" /tmp --bind "$WD" "$WD")
while read -r d; do
  [ -n "$d" ] && [ -d "$d" ] && BW+=(--ro-bind "$d" "$d")
done < <(grep -oE '/tmp/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*/[A-Za-z0-9_.-]+\.png' "$PROMPT" | xargs -r -n1 dirname | sort -u)

"${BW[@]}" -- "$@"
rc=$?

# copy the answers out of the private /tmp
while read -r f; do
  [ -n "$f" ] || continue
  src="$PRIV/${f#/tmp/}"
  [ -f "$src" ] && cp -p "$src" "$f" && echo "reader_sandbox: copied out $f" >&2
done < <(grep -oE '/tmp/[A-Za-z0-9_.-]+\.json' "$PROMPT" | sort -u)
exit $rc
