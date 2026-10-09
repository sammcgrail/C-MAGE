# C-MAGE corpus images

All 2,510 benchmark images (the exact PNGs the Sonnet 5, Sonnet 5.5 and CXMolScribe readers were scored on):
RDKit depictions at 1500 px of PubChem compounds.

**Pixels only since 8 Oct 2026.** RDKit's PNG writer had stored each molecule's SMILES, molblock and pickled
molecule inside its image (zTXt chunks). Every image was rewritten without them; the image data is untouched,
so the pixels are identical (`PIXEL_SHA256`, checked per file). `SHA256SUMS` covers the new bytes; check with
`cd cmage_corpus && sha256sum -c ../SHA256SUMS`.

- `cmage_corpus_part1of3.zip`, `part2of3`, `part3of3`: split only to stay under GitHub's 100 MB file limit.
  Unzip all three into the same folder; they merge into `cmage_corpus/` (2,510 PNGs + `manifest.csv`).
- `manifest.csv`: file, key, compound name, PubChem CID, truth SMILES (PubChem), and which zip part holds it.

Download: https://github.com/sammcgrail/C-MAGE/tree/main/corpus_images (each zip's page has a Download button),
or `git clone` and take the folder.
