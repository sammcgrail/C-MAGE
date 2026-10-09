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
#   - NO NETWORK but the model API (8 Oct): its own network namespace (--unshare-net, loopback only);
#     inside, socat bridges 127.0.0.1:3128 to tools/jail_proxy.py on a unix socket in the launch dir,
#     HTTPS_PROXY points the CLI at it, and the proxy tunnels only CONNECT <*.anthropic.com etc>:443.
#     pip, PubChem, the public site, GitHub, localhost services: no route, or 403 from the proxy. Every
#     request is logged to <launch-dir>/jail_net.jsonl. Over 807 jailed 5.5 readers (29 Sep - 8 Oct)
#     not one used pip, curl or a URL, so nothing a reader legitimately did is lost. Until 8 Oct the
#     network stayed open "for installs", and a Sonnet 5 reader had pip-installed py2opsin with it.
#   - name-to-structure tools hidden: py2opsin (OPSIN, with its jar) and Indigo (nameToStructure; also
#     the renderer of the renderer-control set) are masked inside .venv-ms.
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
HERE=$(cd "$(dirname "$0")" && pwd)
command -v socat >/dev/null || { echo "reader_sandbox: socat missing (apt-get install socat)" >&2; exit 3; }
PROJ=/root/.claude/projects/$(printf '%s' "$WD" | sed 's#[^A-Za-z0-9]#-#g')
mkdir -p "$PROJ"

BW=(bwrap --die-with-parent --unshare-pid --unshare-ipc --unshare-net --cap-drop ALL
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
# ...minus the name-to-structure tools in it (an empty dir imports as nothing)
for d in "$VENV"/lib/python3*/site-packages/{py2opsin,py2opsin-*.dist-info,indigo,epam_indigo-*.dist-info}; do
  [ -d "$d" ] && BW+=(--tmpfs "$d")
done
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

# the only way out: the allowlisting proxy on a unix socket in the launch dir (bound into the jail)
SOCK="$WD/.jail-proxy.sock"; NETLOG="$WD/jail_net.jsonl"
python3 "$HERE/jail_proxy.py" "$SOCK" "$NETLOG" & PXY=$!
trap 'kill $PXY 2>/dev/null' EXIT
for _ in $(seq 50); do [ -S "$SOCK" ] && break; sleep 0.1; done
[ -S "$SOCK" ] || { echo "reader_sandbox: proxy did not start" >&2; exit 3; }
P=http://127.0.0.1:3128
BW+=(--setenv HTTPS_PROXY "$P" --setenv https_proxy "$P" --setenv HTTP_PROXY "$P" --setenv http_proxy "$P"
     --setenv ALL_PROXY "$P" --unsetenv NO_PROXY --unsetenv no_proxy
     --setenv CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC 1)

"${BW[@]}" -- bash -c 'socat TCP-LISTEN:3128,bind=127.0.0.1,reuseaddr,fork UNIX-CONNECT:"$0" 2>/dev/null &
  for _ in $(seq 50); do (exec 3<>/dev/tcp/127.0.0.1/3128) 2>/dev/null && break; sleep 0.1; done
  exec "$@"' "$SOCK" "$@"
rc=$?
kill $PXY 2>/dev/null; wait $PXY 2>/dev/null

# copy the answers out of the private /tmp
while read -r f; do
  [ -n "$f" ] || continue
  src="$PRIV/${f#/tmp/}"
  [ -f "$src" ] && cp -p "$src" "$f" && echo "reader_sandbox: copied out $f" >&2
done < <(grep -oE '/tmp/[A-Za-z0-9_.-]+\.json' "$PROMPT" | sort -u)
exit $rc
