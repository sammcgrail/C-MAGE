"""PNG images handed to a reader carry PIXELS ONLY. No text chunk, ever.

WHY (8 Oct). RDKit's MolDraw2DCairo writes the molecule INTO the PNG it draws: zTXt chunks
"SMILES rdkit <version>", "MOL rdkit <version>" and "rdkitPKL rdkit <version>" (the isomeric SMILES,
the molblock and the pickled molecule). Every corpus_rdkit_1500 image was drawn that way, from its
reference structure, and the blind copy was a byte copy, so every blind image a reader ever opened
held its own answer key one `Chem.MolFromPNGFile()` away. Two audits found no reader ever read it,
but a blind test cannot rest on nobody having looked.

    pixel_only(data)        -> bytes   keep only the chunks that define pixels; IDAT is untouched,
                                       so the decoded image is identical by construction
    text_chunks(data)       -> list    tEXt/zTXt/iTXt keywords present (empty = clean)
    assert_pixel_only(data) -> None    raises PngMetadataError on any chunk outside KEEP
    pixel_hash(data)        -> str     sha256 over mode, size and decoded pixels

    python tools/png_clean.py --selftest
    python tools/png_clean.py --check FILE...      exit 1 if any file carries a text chunk
"""
from __future__ import annotations

import hashlib
import io
import struct
import sys
import zlib

SIG = b"\x89PNG\r\n\x1a\n"
TEXT = {b"tEXt", b"zTXt", b"iTXt"}
# Chunks that define what the image looks like. Everything else (text, eXIf, tIME, private
# chunks) can carry arbitrary bytes and is dropped.
KEEP = {b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND", b"gAMA", b"cHRM", b"sRGB", b"iCCP",
        b"sBIT", b"bKGD", b"pHYs"}


class PngMetadataError(ValueError):
    pass


def chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """(type, the whole chunk incl. length and CRC). Raises on anything that is not a PNG."""
    if not data.startswith(SIG):
        raise PngMetadataError("not a PNG")
    out, i = [], len(SIG)
    while i < len(data):
        if i + 8 > len(data):
            raise PngMetadataError("truncated chunk header")
        n, = struct.unpack(">I", data[i:i + 4])
        t = data[i + 4:i + 8]
        end = i + 12 + n
        if end > len(data):
            raise PngMetadataError(f"truncated {t!r} chunk")
        out.append((t, data[i:end]))
        i = end
        if t == b"IEND":
            break
    if not out or out[-1][0] != b"IEND":
        raise PngMetadataError("no IEND")
    if i != len(data):
        raise PngMetadataError(f"{len(data) - i} trailing bytes after IEND")
    return out


def text_chunks(data: bytes) -> list[str]:
    """Keyword of every tEXt/zTXt/iTXt chunk (e.g. 'SMILES rdkit 2025.03.3')."""
    found = []
    for t, c in chunks(data):
        if t in TEXT:
            body = c[8:-4]
            found.append(t.decode() + ":" + body.split(b"\0", 1)[0].decode("latin1"))
    return found


def foreign_chunks(data: bytes) -> list[str]:
    return [t.decode("latin1") for t, _ in chunks(data) if t not in KEEP]


def pixel_only(data: bytes) -> bytes:
    """Drop every chunk outside KEEP; the IDAT stream is copied byte for byte."""
    return SIG + b"".join(c for t, c in chunks(data) if t in KEEP)


def assert_pixel_only(data: bytes, where: str = "") -> None:
    bad = foreign_chunks(data)
    if bad:
        raise PngMetadataError(f"{where or 'PNG'} carries non-pixel chunk(s) {bad}; "
                               f"text: {text_chunks(data)}")


def pixel_hash(data: bytes) -> str:
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    h = hashlib.sha256(f"{im.mode}|{im.size}|".encode())
    if im.mode == "P":
        h.update(bytes(im.getpalette() or []))
        if "transparency" in im.info:
            h.update(repr(im.info["transparency"]).encode())
    h.update(im.tobytes())
    return h.hexdigest()


def clean_file(path: str) -> tuple[bool, str]:
    """Rewrite PATH pixel-only (atomic). Returns (changed, pixel hash); refuses a pixel change."""
    import os
    data = open(path, "rb").read()
    if not foreign_chunks(data):
        return False, pixel_hash(data)
    new = pixel_only(data)
    before, after = pixel_hash(data), pixel_hash(new)
    if before != after:
        raise PngMetadataError(f"{path}: pixels changed ({before} -> {after}); not written")
    assert_pixel_only(new, path)
    tmp = path + ".pxtmp"
    with open(tmp, "wb") as fh:
        fh.write(new)
    st = os.stat(path)
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, path)
    return True, after


def _selftest() -> int:
    from PIL import Image, PngImagePlugin
    from rdkit import Chem, RDLogger
    from rdkit.Chem.Draw import rdMolDraw2D
    RDLogger.DisableLog("rdApp.*")
    fails = 0

    def check(name, ok):
        nonlocal fails
        print(("  ok   " if ok else "  FAIL ") + name)
        fails += 0 if ok else 1

    def draw(smi, meta):
        d = rdMolDraw2D.MolDraw2DCairo(400, 400)
        o = d.drawOptions()
        o.clearBackground, o.maxFontSize, o.minFontSize = True, -1, -1
        o.scaleBondWidth, o.bondLineWidth = True, 2
        if not meta:
            o.includeMetadata = False
        rdMolDraw2D.PrepareAndDrawMolecule(d, Chem.MolFromSmiles(smi))
        d.FinishDrawing()
        return d.GetDrawingText()

    smi = "C[C@H](N)C(=O)O"
    raw = draw(smi, True)
    # positive control: the leak is real, and RDKit can read it back
    check("control: RDKit default render carries a text chunk", bool(text_chunks(raw)))
    m = Chem.MolFromPNGString(raw)
    check("control: MolFromPNGString recovers the answer", m is not None and
          Chem.MolToSmiles(m) == Chem.MolToSmiles(Chem.MolFromSmiles(smi)))
    clean = pixel_only(raw)
    check("pixel_only drops every text chunk", text_chunks(clean) == [] and not foreign_chunks(clean))
    check("pixel_only keeps the pixels", pixel_hash(clean) == pixel_hash(raw))
    try:
        back = Chem.MolFromPNGString(clean)
    except Exception:
        back = None
    check("MolFromPNGString finds nothing after cleaning", back is None)
    check("includeMetadata=False render == pixel_only(default render), byte for byte",
          draw(smi, False) == clean)
    try:
        assert_pixel_only(raw, "raw")
        check("assert_pixel_only refuses the RDKit render", False)
    except PngMetadataError:
        check("assert_pixel_only refuses the RDKit render", True)
    # a PIL-written tEXt and an iTXt, and an unknown private chunk, are all refused
    bio = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "CCO")
    info.add_itxt("SMILES", "CCO", zip=True)
    Image.new("RGB", (8, 8), "white").save(bio, "PNG", pnginfo=info)
    p = bio.getvalue()
    check("PIL tEXt + iTXt detected", len(text_chunks(p)) == 2)
    priv = p[:-12] + struct.pack(">I", 3) + b"leAK" + b"CCO" + \
        struct.pack(">I", zlib.crc32(b"leAKCCO") & 0xFFFFFFFF) + p[-12:]
    check("private chunk is foreign", "leAK" in foreign_chunks(priv))
    check("private chunk stripped, pixels kept", not foreign_chunks(pixel_only(priv))
          and pixel_hash(pixel_only(priv)) == pixel_hash(p))
    try:
        chunks(b"GIF89a")
        check("non-PNG refused", False)
    except PngMetadataError:
        check("non-PNG refused", True)
    print("PNG_CLEAN SELFTEST " + ("PASS" if not fails else f"FAIL ({fails})"))
    return 1 if fails else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        sys.exit(_selftest())
    if sys.argv[1:2] == ["--check"]:
        bad = 0
        for f in sys.argv[2:]:
            t = foreign_chunks(open(f, "rb").read())
            if t:
                bad += 1
                print(f"{f}: {t}")
        print(f"{len(sys.argv) - 2 - bad} clean, {bad} carrying non-pixel chunks")
        sys.exit(1 if bad else 0)
    print(__doc__)
    sys.exit(2)
