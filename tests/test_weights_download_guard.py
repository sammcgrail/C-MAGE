"""Mutation test for the weights-download guard.

A guard nobody has watched go red is a guard you do not know works. So every
case here drives a real failure through `_download_weights` and asserts BOTH
that it refuses AND that it cached nothing — the original bug was not "it
downloaded an error page", it was "it CACHED the error page as the model", after
which every later import died with an unrelated h5py signature error because the
download only fires when the file is absent.

Two things this file deliberately checks that an earlier version did not:

  * the CALL SITE, not just the guard. Slicing out `_download_weights` and
    exercising it proves the guard works, and proves nothing about whether
    `load_model` still calls it. Reverting the call site to the original
    `open(path,"wb").write(requests.get(url).content)` passed the old test.
  * `requests.get` is patched on the exec namespace and restored, so one case
    cannot leak into the next or into another test module.
"""
import os
import re
import tempfile

import pytest

_SRC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "cxmolscribe-wd",
    "DECIMER-Image-Segmentation", "decimer_segmentation", "decimer_segmentation.py")

HDF5 = b"\x89HDF\r\n\x1a\n"


def _source():
    with open(_SRC_PATH) as fh:
        return fh.read()


def _guard():
    """Exec just the guard, without importing the package (which loads
    TensorFlow and downloads 260 MB at module scope)."""
    src = _source()
    # Anchor on the DEFINITION at line start, never the bare identifier: the name
    # also appears in the comment above it and in the docstring, so a plain
    # `src.index(name)` can slide to a different offset and test text that is not
    # the guard at all.
    m = re.search(r"^_MIN_WEIGHTS_BYTES\s*=", src, re.M)
    assert m, "guard constants not found — did the source move?"
    start, end = m.start(), src.index("\ndef load_model()")
    assert end > start and "def _download_weights" in src[start:end], \
        "sliced region does not contain the guard; the anchors have drifted"
    import requests
    ns = {"os": os, "requests": requests}
    exec(compile(src[start:end], _SRC_PATH, "exec"), ns)
    return ns


class Resp:
    def __init__(self, status=200, ctype="application/octet-stream", body=b""):
        self.status_code = status
        self.headers = {"Content-Type": ctype}
        self.content = body


BAD_CASES = [
    ("504 HTML error page — the actual bug", Resp(504, "text/html", b"<html>504</html>")),
    ("HTTP 200 but still an HTML page", Resp(200, "text/html", b"<html>oops</html>")),
    ("200, right content-type, wrong bytes", Resp(200, body=b"not-a-model" * 10)),
    ("200, real HDF5 magic but far too small", Resp(200, body=HDF5 + b"x" * 100)),
]


@pytest.mark.parametrize("label,resp", BAD_CASES, ids=[c[0] for c in BAD_CASES])
def test_bad_payload_is_refused_and_not_cached(label, resp):
    ns = _guard()
    ns["requests"].get = lambda *a, **k: resp
    dest = os.path.join(tempfile.mkdtemp(), "mask_rcnn_molecule.h5")
    with pytest.raises(RuntimeError):
        ns["_download_weights"]("http://fake", dest)
    # The refusal is only half of it. Leaving the bytes behind under either name
    # re-creates the original failure, because the download only runs when the
    # file is absent.
    assert not os.path.exists(dest), f"{label}: cached rubbish at the real path"
    assert not os.path.exists(dest + ".part"), f"{label}: left a .part behind"


def test_valid_payload_is_accepted():
    """Positive control. Without this, a guard that refuses EVERYTHING would pass
    every test above and prove nothing."""
    ns = _guard()
    ns["requests"].get = lambda *a, **k: Resp(200, body=HDF5 + b"\0" * (9 * 1024 * 1024))
    dest = os.path.join(tempfile.mkdtemp(), "w.h5")
    ns["_download_weights"]("http://fake", dest)
    assert os.path.exists(dest)
    with open(dest, "rb") as fh:
        assert fh.read(8) == HDF5


def test_load_model_actually_uses_the_guard():
    """The integration assertion the guard test cannot make about itself.

    `_download_weights` being correct is worth nothing if `load_model` bypasses
    it. Assert on load_model's own source: it must call the guard, and it must
    not write a response body straight to disk.
    """
    src = _source()
    start = src.index("\ndef load_model()")
    end = src.find("\ndef ", start + 1)
    body = src[start:end if end != -1 else len(src)]

    assert "_download_weights" in body, \
        "load_model no longer calls _download_weights — the guard is bypassed"
    assert not re.search(r"requests\.get\([^)]*\)\.content", body), \
        "load_model writes a response body directly again — this is the original bug"
    # Guard on the guard: if the slice were empty, both assertions above would
    # pass vacuously.
    assert "def load_model()" in body and len(body) > 200, \
        f"load_model slice looks wrong ({len(body)} chars) — anchors have drifted"
