# Upstream defects found while benchmarking

Written for the C-MAGE / DECIMER-Image-Segmentation maintainers. Every claim below
was measured on this fork, whose stage-2 tree is byte-identical to upstream except
for the vendored `DECIMER_BBOX_PAD` branch and the removed Zenodo download. Line
numbers are from the files as they sit in `cxmolscribe-wd/`.

---

## 1. Red and blue are swapped in every segment PNG

**Where:** `cxmolscribe-wd/DECIMER-Image-Segmentation/pipeline_dis.py:84`

```python
for numeral, img in enumerate(segments):
    img_var = Image.fromarray(img)          # <- img is BGR(A), PIL reads it as RGB(A)
```

**Why:** `decimer_segmentation.py:73` loads a non-PDF input with

```python
images = [cv2.imread(file_path)]            # OpenCV returns BGR
```

so for the image-file path — which is the path C-MAGE always takes, because stage 1
writes PNG figures — the array that reaches `Image.fromarray` is BGR. PIL interprets
it as RGB and writes the file with the red and blue channels exchanged.

The round trip then hides it. Stage 3 reads the segment with
`MolScribe/molscribe/interface.py:154-155`:

```python
image = cv2.imread(path)
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
```

which faithfully reproduces what the PNG says — so the model sees the swapped
colours, and nothing in the pipeline ever compares a segment back to its source.

**Measured.** Locating each segment inside its source figure by matching on the
GREEN channel only — which an R↔B swap leaves untouched — and then comparing all
three channels at that offset:

| figure | ink px | match as written | match with R,B swapped |
|---|---|---|---|
| PMC11227129_..._image_1 | 3,740 | 2,321 | **3,740 (100.000%)** |
| PMC11227129_..._image_1 (2nd segment) | 1,977 | 84 | **1,977 (100.000%)** |
| PMC13390035_..._image_1 | 378 | 160 | **378 (100.000%)** |
| PMC9185882_..._image_1 | 179 | 12 | **179 (100.000%)** |

Over 1,914 segments from 20 document runs: **1,010 (52.8%) carry colour**
(`|R−B| > 20` on at least one ink pixel), and **21.25% of all segment ink pixels**
(2,465,543 of 11,600,042) are affected. Pure black-on-white line art is unaffected,
which is why this survives on the usual test images.

**Root cause is really an inconsistency two lines apart.** `decimer_segmentation.py`
returns a different channel order depending on the input type:

```python
# 65-71  PDF input   -> pdf2image -> PIL -> np.array(...)   = RGB
# 73     image input -> cv2.imread(...)                     = BGR
```

Everything downstream is correct for exactly one of those.

---

## 2. The Otsu threshold that builds the mask runs on a wrongly-weighted greyscale

**Where:** `cxmolscribe-wd/DECIMER-Image-Segmentation/decimer_segmentation/decimer_segmentation.py:436`

```python
im_gray = cv2.cvtColor(masked_image, cv2.COLOR_RGB2GRAY)
_, im_bw = cv2.threshold(im_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
```

`masked_image` came from the same `cv2.imread` above, so on the image-file path it is
BGR, and `COLOR_RGB2GRAY` applies the red weight (0.299) to the blue channel and the
blue weight (0.114) to the red one. The resulting binary image is what becomes the
alpha channel, so **for any coloured structure the mask boundary is decided by a
luminance that is wrong by construction** — red ink is treated as three times fainter
than it is, blue ink as three times stronger.

This compounds with the fixed binarisation at `complete_structure.py:282`
(`binarize_image(image_array, threshold=0.72)`, overriding the Otsu default at `:25`),
which is already the main driver of ink loss.

---

## 3. `apply_mask` with a bbox pad returns the crop UNMASKED

**Where:** `decimer_segmentation/decimer_segmentation.py:313` (`apply_mask`), the
`DECIMER_BBOX_PAD > 0` branch, which returns `image[y0:y1, x0:x1]` without applying
the mask at all.

This is worth documenting because it makes the two obvious remedies
non-comparable: any positive pad already recovers **100%** of the ink that the mask
would have whitened inside the crop rectangle, so "pad the bbox" and "dilate the
mask" are not two settings of the same dial. Measured on 88 structure-bearing real
figures, mask dilation's entire ceiling is **+2.6 points** of retained ink
(48.0% → 50.6%); `DECIMER_BBOX_PAD=0.15` reaches 58.3%, but 26.8% of the newly
included ink belongs to a *different* segment and most of the remainder is body text.
Higher retention there is not better recognition.

---

## What is NOT a bug, contrary to our own earlier report

We previously measured "stage 2 destroys most real figures — median 29.1% of figure
ink retained, 27% of figures produce zero segments" and traced it to the 0.72
binarisation. That number's denominator was wrong. Classifying all 139 stage-1
figures by eye (twice, independently, agreeing exactly) shows **44 of 139 (32%)
contain no chemistry at all** — body text, data tables, IR spectra, journal
boilerplate. Restricted to the 95 figures that carry a drawn structure:

| | all 139 | structure-bearing 95 |
|---|---|---|
| zero-segment figures | 26.6% | **4.2%** |
| median ink retained | 0.291 | **0.590** |

Segmentation is a good filter: 75% of non-chemistry figures produce no segment and
only 0.9% of non-chemistry ink survives. And on the drawings it does engage with, it
keeps **96.2%–99.8%** of their ink.

The real remaining costs are (1) the colour bugs above, (2) detection — structures it
never engages with, and (3) 11 non-chemistry figures that DO leak 15 false-positive
segments into stage 3. Not the masking.
