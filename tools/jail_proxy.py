"""The reader jail's ONLY way out: an HTTPS CONNECT proxy on a unix socket, allowlisted to the
Anthropic API (8 Oct).

    jail_proxy.py <socket-path> <log-path>          serve until killed (SIGTERM)
    jail_proxy.py --selftest

WHY. Until 8 Oct the jail (tools/reader_sandbox.sh) shared the host's network: "the CLI needs the API,
and the reader rule allows package installs; lookups are the scanner's job". A scanner only sees what
it has a rule for. The audit found a Sonnet 5 reader that pip-installed py2opsin and turned names it
typed from memory into structures, a door no rule covered, and the public site served every reference
SMILES. Over 807 jailed Sonnet 5.5 readers (29 Sep - 8 Oct) not one used pip, curl or any URL, so
readers need nothing but the model API. Now the jail has its own network namespace with only
loopback; inside it, socat bridges 127.0.0.1:3128 to this socket, HTTPS_PROXY points the CLI at it,
and this proxy opens a tunnel only for CONNECT <allowed host>:443. Everything else gets 403 and a
log line; a direct connection has no route at all.

The log (one JSON line per request: time, target, allowed) sits in the launch dir beside the reader's
output, so what a reader tried to reach is evidence, not a guess.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time

# Hosts the Claude Code CLI needs: the API, and OAuth/account endpoints for a token refresh.
ALLOW_EXACT = {"api.anthropic.com", "console.anthropic.com", "platform.claude.com", "claude.ai"}
ALLOW_SUFFIX = (".anthropic.com", ".claude.com", ".claude.ai")
# claude.ai MCP connectors (mail, drive, docs ...) load through this host: a reader needs none of them,
# and a connector is a way to reach data that is not the image.
DENY_EXACT = {"mcp-proxy.anthropic.com"}
PORTS = {443}


def allowed(host: str, port: int) -> bool:
    host = host.lower().rstrip(".")
    if port not in PORTS or not host or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in host):
        return False
    if host in DENY_EXACT:
        return False
    return host in ALLOW_EXACT or host.endswith(ALLOW_SUFFIX)


def parse_connect(head: bytes) -> tuple[str, int] | None:
    """'CONNECT host:443 HTTP/1.1' -> (host, 443); anything else (GET http://..., a bare IP:port with
    no CONNECT, a malformed line) -> None, which is refused."""
    try:
        line = head.split(b"\r\n", 1)[0].decode("ascii")
        method, target, _ = line.split(" ", 2)
        if method != "CONNECT":
            return None
        host, port = target.rsplit(":", 1)
        return host.strip("[]"), int(port)
    except Exception:
        return None


class Proxy:
    def __init__(self, log_path: str):
        self.log = open(log_path, "a", buffering=1)

    def note(self, target: str, ok: bool, why: str = "") -> None:
        self.log.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                   "target": target[:200], "allowed": ok, **({"why": why} if why else {})}) + "\n")

    async def pipe(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        try:
            while True:
                b = await r.read(65536)
                if not b:
                    break
                w.write(b)
                await w.drain()
        except Exception:
            pass
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def handle(self, cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
        try:
            head = await asyncio.wait_for(cr.readuntil(b"\r\n\r\n"), 30)
        except Exception:
            cw.close()
            return
        tgt = parse_connect(head)
        first = head.split(b"\r\n", 1)[0].decode("latin1")
        if tgt is None or not allowed(*tgt):
            self.note(first, False, "not CONNECT" if tgt is None else "host not allowed")
            cw.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await cw.drain()
            cw.close()
            return
        try:
            ur, uw = await asyncio.wait_for(asyncio.open_connection(*tgt), 30)
        except Exception as e:
            self.note(first, True, f"upstream failed: {type(e).__name__}")
            cw.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await cw.drain()
            cw.close()
            return
        self.note(first, True)
        cw.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await cw.drain()
        await asyncio.gather(self.pipe(cr, uw), self.pipe(ur, cw))


async def serve(sock: str, log_path: str) -> None:
    p = Proxy(log_path)
    if os.path.exists(sock):
        os.unlink(sock)
    server = await asyncio.start_unix_server(p.handle, path=sock)
    os.chmod(sock, 0o600)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, stop.set)
    async with server:
        await stop.wait()
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass


def selftest() -> int:
    fails = 0

    def check(name, ok):
        nonlocal fails
        print(("  ok   " if ok else "  FAIL ") + name)
        fails += 0 if ok else 1

    check("api.anthropic.com:443 allowed", allowed("api.anthropic.com", 443))
    check("API on port 80 refused", not allowed("api.anthropic.com", 80))
    for h in ("pubchem.ncbi.nlm.nih.gov", "pypi.org", "files.pythonhosted.org", "cmage.sebland.com",
              "github.com", "raw.githubusercontent.com", "opsin.ch.cam.ac.uk", "cactus.nci.nih.gov",
              "www.ebi.ac.uk", "localhost", "127.0.0.1", "anthropic.com.evil.org", "evilanthropic.com",
              "api.anthropic.com@evil.org", "api.anthropic.com/x", "mcp-proxy.anthropic.com"):
        check(f"{h} refused", not allowed(h, 443))
    check("CONNECT parsed", parse_connect(b"CONNECT api.anthropic.com:443 HTTP/1.1\r\nHost: x\r\n\r\n")
          == ("api.anthropic.com", 443))
    check("absolute-form GET refused", parse_connect(b"GET http://api.anthropic.com/ HTTP/1.1\r\n\r\n") is None)
    check("garbage refused", parse_connect(b"\x16\x03\x01junk\r\n\r\n") is None)
    print("JAIL_PROXY SELFTEST " + ("PASS" if not fails else f"FAIL ({fails})"))
    return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        sys.exit(selftest())
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    asyncio.run(serve(sys.argv[1], sys.argv[2]))
