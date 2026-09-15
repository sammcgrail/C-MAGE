#!/usr/bin/env python3
"""MolScribe worker for the C-MAGE MCP server. Run it with the repo's MolScribe venv (.venv-ms).

Protocol, one JSON object per line:
- The worker loads the model once and prints {"ready": true}, or {"ready": false, "error": ...}.
- The server sends {"id": n, "path": "/abs/image.png"}.
- The worker replies {"id": n, "smiles": ..., "plain_smiles": ..., "canonical_smiles": ...,
  "valid": bool, "confidence": float}, or {"id": n, "error": ...}.

stdout is the protocol channel, so everything else, including anything molscribe or torch
print, is redirected to stderr before the model loads.
"""
import json
import os
import sys

PROTO = sys.stdout
sys.stdout = sys.stderr


def send(obj: dict) -> None:
    PROTO.write(json.dumps(obj) + "\n")
    PROTO.flush()


def main() -> int:
    try:
        import torch
        from huggingface_hub import hf_hub_download
        from molscribe import MolScribe
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        weights = hf_hub_download("yujieq/MolScribe", "swin_base_char_aux_1m.pth")
        device = torch.device(os.environ.get("CMAGE_MS_DEVICE", "cpu"))
        model = MolScribe(weights, device)
    except Exception as e:                      # report and exit; the server surfaces the message
        send({"ready": False, "error": f"{type(e).__name__}: {e}"})
        return 1
    send({"ready": True})
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        try:
            pred = model.predict_image_file(req["path"], return_atoms_bonds=False, return_confidence=True)
            smiles = pred.get("smiles")
            # A CXSMILES carries its extension block after a space: "*C |$Ph;$|".
            plain = smiles.split(" |")[0] if isinstance(smiles, str) else smiles
            mol = Chem.MolFromSmiles(plain) if plain and plain != "<invalid>" else None
            send({"id": req["id"], "smiles": smiles, "plain_smiles": plain,
                  "canonical_smiles": Chem.MolToSmiles(mol) if mol is not None else None,
                  "valid": mol is not None, "confidence": pred.get("confidence")})
        except Exception as e:
            send({"id": req.get("id"), "error": f"{type(e).__name__}: {e}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
