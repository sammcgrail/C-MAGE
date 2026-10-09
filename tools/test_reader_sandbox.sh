#!/usr/bin/env bash
# Selftest for reader_sandbox.sh, no model needed (~2 s). Must print SANDBOX SELFTEST PASS.
# Every denial is paired with a POSITIVE CONTROL run outside the sandbox: the same probe must
# SUCCEED on the host, so an "empty" result inside can only mean the jail hid it (a probe that
# found nothing because the path moved would fail the control instead of passing quietly).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
PY=/root/C-MAGE/.venv-ms/bin/python
T=$(mktemp -d /tmp/sbxself.XXXXXX); mkdir -p "$T/blind"
"$PY" -c "from rdkit import Chem; from rdkit.Chem import Draw; Draw.MolToFile(Chem.MolFromSmiles('CC(=O)Oc1ccccc1C(=O)O'),'$T/blind/fig01.png',size=(400,400))"
echo "junk" > /tmp/sbxself_leak.txt                      # a host /tmp file the reader must not see
printf 'images: %s/blind/fig01.png\nanswers: /tmp/%s_ans.json\n' "$T" "${T#/tmp/}" > "$T/prompt.txt"
WD=$(mktemp -d /tmp/reader-launch.XXXXXX); PRIV=$(mktemp -d /tmp/reader-tmp.XXXXXX)
fails=0
check() { if [ "$2" = 1 ]; then echo "  ok   $1"; else echo "  FAIL $1"; fails=$((fails+1)); fi; }
inside() { "$HERE/reader_sandbox.sh" "$WD" "$PRIV" "$T/prompt.txt" -- bash -c "$1" 2>/dev/null; }
host() { bash -c "$1" 2>/dev/null; }
probe() {  # name, command whose output must be NON-EMPTY on the host and EMPTY in the jail
  local h i; h=$(host "$2"); i=$(inside "$2")
  check "control: host sees $1" "$([ -n "$h" ] && echo 1)"
  check "jail hides $1" "$([ -z "$i" ] && echo 1)"
}
probe "the answer key (benchmarks)"   "ls /root/C-MAGE/benchmarks | head -3"
probe "the lane state (cmage-work)"   "ls /root/cmage-work | head -3"
probe "corpus copies (preserve)"      "ls /root/cmage-tmp-preserve | head -3"
probe "other transcripts"             "ls /root/.claude/projects | grep -v reader-launch | head -3"
probe "host /tmp files"               "ls /tmp/sbxself_leak.txt"
probe "seb transcripts"               "ls /root/seb/transcripts | head -3"
probe "host view via /proc/1/root"    "ls /proc/1/root/root/C-MAGE/benchmarks | head -3"
probe "python listdir of the repo"    "$PY -c \"import os; print([x for x in os.listdir('/root/C-MAGE') if x != '.venv-ms'] or '')\" | tr -d \"'\" | grep -v '^\$'"
check "cannot unmount a mask"   "$(inside 'umount /root/C-MAGE 2>/dev/null && echo broke' | grep -q broke || echo 1)"
check "docker socket dead"      "$(inside 'docker ps >/dev/null 2>&1 && echo broke' | grep -q broke || echo 1)"
# NETWORK (8 Oct): only the model API, through the proxy. Each "jail refuses" is paired with a host
# control that reaches the same URL, so a refusal cannot be an outage.
code() { echo "$1" | tail -c 4 | grep -qE '^[1-5][0-9][0-9]$'; }
net() {  # name, curl args: host must get an HTTP status, the jail must not
  local h i; h=$(host "curl -s -o /dev/null -w %{http_code} --max-time 12 $2"); i=$(inside "curl -s -o /dev/null -w %{http_code} --max-time 12 $2")
  check "control: host reaches $1 ($h)" "$(code "$h" && [ "$h" != 000 ] && echo 1)"
  check "jail cannot reach $1 ($i)" "$([ "$i" = 000 ] && echo 1)"
}
net "PubChem"                 "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/property/IsomericSMILES/TXT"
net "PubChem, proxy bypassed" "--noproxy '*' https://pubchem.ncbi.nlm.nih.gov/"
net "pypi"                    "https://pypi.org/simple/py2opsin/"
net "the public site"         "https://cmage.sebland.com/wall/images.json"
net "GitHub raw"              "https://raw.githubusercontent.com/sammcgrail/C-MAGE/main/README.md"
net "the local webapp"        "--noproxy '*' http://127.0.0.1:20079/api/health"
api=$(inside "curl -s -o /dev/null -w %{http_code} --max-time 15 https://api.anthropic.com/v1/models")
check "the model API IS reachable through the proxy ($api)" "$([ "$api" = 401 ] && echo 1)"
check "denials are logged" "$(grep -q '"allowed": false' "$WD/jail_net.jsonl" 2>/dev/null && echo 1)"
# name-to-structure tools hidden, with host controls
check "control: host imports py2opsin" "$(host "$PY -c 'from py2opsin import py2opsin; print(1)'" | grep -qx 1 && echo 1)"
check "jail cannot import py2opsin"    "$(inside "$PY -c 'from py2opsin import py2opsin; print(1)'" | grep -qx 1 || echo 1)"
check "control: host imports Indigo"   "$(host "$PY -c 'from indigo import Indigo; print(1)'" | grep -qx 1 && echo 1)"
check "jail cannot import Indigo"      "$(inside "$PY -c 'from indigo import Indigo; print(1)'" | grep -qx 1 || echo 1)"
# the method's tools must still be there
check "RDKit at the prompt's path" "$(inside "$PY -c \"from rdkit import Chem; print(Chem.MolToSmiles(Chem.MolFromSmiles('OCC')))\"" | grep -qx CCO && echo 1)"
check "blind image readable"       "$(inside "test -s $T/blind/fig01.png && echo y" | grep -qx y && echo 1)"
check "blind dir read-only"        "$(inside "touch $T/blind/x 2>/dev/null && echo broke" | grep -q broke || echo 1)"
check "venv read-only"             "$(inside "touch /root/C-MAGE/.venv-ms/x 2>/dev/null && echo broke" | grep -q broke || echo 1)"
check "osra runs"                  "$(inside "osra $T/blind/fig01.png" | grep -q . && echo 1)"
# answers written in the private /tmp come back out, with the reader's mtime
rm -f "/tmp/${T#/tmp/}_ans.json"
inside "echo '[]' > /tmp/${T#/tmp/}_ans.json" >/dev/null
check "answers copied out"         "$([ -f "/tmp/${T#/tmp/}_ans.json" ] && echo 1)"
rm -rf "$T" "$WD" "$PRIV" /tmp/sbxself_leak.txt "/tmp/${T#/tmp/}_ans.json"
rmdir "/root/.claude/projects/$(printf '%s' "$WD" | sed 's#[^A-Za-z0-9]#-#g')" 2>/dev/null
[ $fails = 0 ] && echo "SANDBOX SELFTEST PASS" || { echo "SANDBOX SELFTEST FAIL ($fails)"; exit 1; }
