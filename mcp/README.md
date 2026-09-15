# C-MAGE MCP server

An [MCP](https://modelcontextprotocol.io) server, built on [FastMCP](https://gofastmcp.com),
that exposes C-MAGE's structure recognition to any MCP client: Claude Code, Claude Desktop,
Cursor and others.

| Tool | What it does |
|---|---|
| `cmage_upload` | Submits a PDF or image to the full C-MAGE pipeline and returns a job id at once. Runs are private unless `publish=true`. |
| `cmage_job` | Returns a job's status and, once it is done, every structure found: `cxsmiles`, `smiles`, `expanded_smiles`, confidence, tier, validity and image links. |
| `cmage_delete` | Deletes a finished run. Needs the `owner_token` from `cmage_upload`. |
| `molscribe_read` | Reads one image with MolScribe directly, with no figure extraction or segmentation. Returns the SMILES as emitted, plain, and RDKit-canonical, plus validity and confidence. |
| `sonnet_read` | Reads one image with a single bare Sonnet API call, with no tools and no agent loop. Returns the SMILES, the name if recognised, a confidence, token usage and an estimated cost at list price. |

MolScribe runs in a persistent worker under the repo's `.venv-ms`, so torch stays out of this
server's environment and the weights load once, not per call. The `cmage_*` tools go
through the webapp's own job API (`CMAGE_URL`), so they get its limits, queue, privacy
defaults and owner tokens for free.

## Setup

```bash
cd /root/C-MAGE
uv venv mcp/.venv --python 3.12
uv pip install --python mcp/.venv/bin/python -r mcp/requirements.txt
```

## Run

```bash
mcp/.venv/bin/python mcp/server.py                      # stdio (for a local client)
mcp/.venv/bin/python mcp/server.py --http --port 8799   # streamable HTTP on 127.0.0.1
```

Connect Claude Code (stdio):

```bash
claude mcp add cmage -e ANTHROPIC_API_KEY=... -- /root/C-MAGE/mcp/.venv/bin/python /root/C-MAGE/mcp/server.py
```

## Environment

| Variable | Default | |
|---|---|---|
| `CMAGE_URL` | `http://127.0.0.1:20079` | the webapp the `cmage_*` tools call |
| `CMAGE_MS_PYTHON` | `.venv-ms/bin/python` | a python with molscribe, torch and rdkit |
| `ANTHROPIC_API_KEY` | none | needed by `sonnet_read` |
| `OPENROUTER_API_KEY` | none | fallback for `sonnet_read` when there is no Anthropic key |
| `CMAGE_SONNET_MODEL` | `claude-sonnet-5` | |
| `CMAGE_MS_DEVICE` | `cpu` | |

## Security

- **The HTTP transport has no authentication.** It binds 127.0.0.1 only. Before it is
  reachable from anywhere else, put auth in front of it: FastMCP supports bearer and
  OAuth providers.
- **Path inputs are refused on the HTTP transport.** A `path` argument on a server someone
  else can reach is an arbitrary file read. Over HTTP, send `content_base64` instead.
- **Uploads are private by default,** as in the webapp. The `owner_token` is returned once,
  by `cmage_upload`, and is the only way to delete the run later.
- **`sonnet_read` spends API credit** on every call; each result reports its estimated cost.

## Tests

```bash
mcp/.venv/bin/python -m pytest mcp/test_server.py -q
```

The offline tests always run. The live tests skip without what they need:
- MolScribe: `.venv-ms`
- the pipeline round trip: the webapp. It uploads a private job and deletes it afterwards.
- Sonnet: an API key.
