"""Mutation test for the weights-download guard. A guard nobody has watched go
red is a guard you do not know works — so drive every branch with a fake
response and assert BOTH that it refuses AND that it cached nothing."""
import sys, types, os, tempfile
sys.modules.setdefault('tensorflow', types.ModuleType('tensorflow'))

# import the module's guard without importing the package (which loads TF and
# would try to download at module scope)
import importlib.util
spec = importlib.util.spec_from_file_location("dis_mod", os.path.join(os.path.dirname(__file__), "..", "cxmolscribe-wd", "DECIMER-Image-Segmentation", "decimer_segmentation", "decimer_segmentation.py"))
src = open(os.path.join(os.path.dirname(__file__), "..", "cxmolscribe-wd", "DECIMER-Image-Segmentation", "decimer_segmentation", "decimer_segmentation.py")).read()
start = src.index("_MIN_WEIGHTS_BYTES")
end = src.index("def load_model()")
ns = {"os": os}
import requests as _rq
ns["requests"] = _rq
exec(src[start:end], ns)
dl = ns["_download_weights"]

class Resp:
    def __init__(self, status=200, ctype="application/octet-stream", body=b""):
        self.status_code, self.headers, self.content = status, {"Content-Type": ctype}, body

HDF5 = b"\x89HDF\r\n\x1a\n"
CASES = [
    ("the real bug: 504 HTML error page", Resp(504, "text/html", b"<html>504</html>")),
    ("HTTP 200 but still an HTML page",   Resp(200, "text/html", b"<html>oops</html>")),
    ("200, right type, wrong bytes",      Resp(200, "application/octet-stream", b"not-a-model" * 10)),
    ("200, real HDF5 magic but tiny",     Resp(200, "application/octet-stream", HDF5 + b"x" * 100)),
]
fails = 0
for name, resp in CASES:
    ns["requests"].get = lambda *a, **k: resp
    d = tempfile.mkdtemp()
    dest = os.path.join(d, "mask_rcnn_molecule.h5")
    try:
        dl("http://fake", dest)
        print(f"  NOT CAUGHT  {name}"); fails += 1
    except RuntimeError as e:
        cached = os.path.exists(dest) or os.path.exists(dest + ".part")
        status = "cached rubbish anyway!" if cached else "nothing cached"
        if cached: fails += 1
        print(f"  caught      {name:34s} -> {str(e).splitlines()[0][46:100]} | {status}")

# positive control: a valid-looking payload MUST be accepted, or the guard is
# just refusing everything and proves nothing.
ns["requests"].get = lambda *a, **k: Resp(200, "application/octet-stream", HDF5 + b"\0" * (9 * 1024 * 1024))
d = tempfile.mkdtemp(); dest = os.path.join(d, "w.h5")
dl("http://fake", dest)
ok = os.path.exists(dest) and open(dest, "rb").read(8) == HDF5
print(f"  ACCEPTED    a valid HDF5 payload -> {ok}")
if not ok: fails += 1
print("\nRESULT:", "all branches fire correctly" if fails == 0 else f"{fails} PROBLEM(S)")
sys.exit(1 if fails else 0)
