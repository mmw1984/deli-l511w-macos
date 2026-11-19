# Local verification

Commands and generated `build/` paths below are relative to the repository root.

## Empirical mono calibration

Supersedes the mono limitation/results in the v2 section below.
`python3 tools/derive_mono.py` samples the gray ramp at 61 interior rows,
takes per-level medians, anchors black/white with flat regions, and interpolates
the seven clipped levels. Result: monotonic, max step5, max second difference3.
The measured eight color bars are `[76,150,29,179,105,226,0,189]`.
Model sum-squared errors on those bars:

| Weights | LUT before luminance | LUT after luminance |
|---|---:|---:|
| 0.299/0.587/0.114 | 0 | 14437 |
| 0.3/0.59/0.11 | 3 | 14399 |
| 0.2126/0.7152/0.0722 | 3258 | 11250 |
| 77/150/29 over256 | 4 | 14586 |
| 19595/38470/7471 over65536 | 0 | 14437 |

The final integer model is used. The tied decimal BT.601 model cannot be
discriminated by these bar samples. W8 applies the LUT directly; RGB24 Gray/Mono
applies it to each channel before luminance. The PPD now requests RGB24 in Gray
mode to preserve channels until that operation. Color output is unchanged.

`make compare-golden` completed with all16 normalized record comparisons
identical; the previously failing mono results are now:

```text
band_mono_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/1-component/DRI-row (inferred) payloads=27/27 identical PSNR=infdB
color_mono_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/1-component/DRI-row (inferred) payloads=23/27 identical PSNR=80.73dB
gray_mono_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/1-component/DRI-row (inferred) payloads=23/27 identical PSNR=79.64dB
PASS: all 16 golden streams parsed, decoded and compared; dynamic metadata masked
```

Every mono job now has a minimum45dB assertion in the comparison test.
Other job results are unchanged from the v2 table below. Actual `make test`:

```text
PASS: empirical mono LUT monotonic, max step=5, max second difference=3
ROUNDTRIP rgb: 2 pages, 3 bands/page, max-channel MAE=2.645 < 8 PASS
ROUNDTRIP gray: 2 pages, 3 bands/page, max-channel MAE=0.235 < 8 PASS
PASS: full/partial bands and row-token boundaries (11 heights)
PASS: RGB24 mono LUT-before-luminance; Gray/Mono aliases; empty/truncated/invalid mode rejected
PASS: 105 paper/media/quality combinations
PASS: PJL metadata injection sanitized
PASS: file/stdin input; empty, truncated, unsupported raster/options/copies rejected
PASS: every binary byte mutation rejected (except legal A4->A5); truncation/trailing/PJL corruption rejected
ALL TESTS PASSED; visual evidence: build/test/comparison.png
```

Viewed the regenerated `build/test/comparison.png`: calibrated gray reference
and decoded output align, as do RGB panels. The gray reference panel is after
the intentional LUT, not the original uncalibrated ramp.
`cupstestppd -I filters` still reports PASS with the same LetterCustom and Photo4x6
naming warnings printed in the next section. No Mac/CUPS queue or printer test.

## v2 Windows golden validation

This section supersedes the pre-golden results below. All 16 v2 PRNs parse and
decode. Source pixel hashes and capture hashes match the manifest. Normalized
non-image records match for all 16 (file-ID/time masked; image checksum/length
validated separately). JPEG headers were stripped by Windows, so table identity
is inferred, not directly compared. Component count, sampling and restart-row
settings are supported by exact entropy matches. Full actual comparison output:

```text
band_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=27/27 identical PSNR=infdB
band_mono_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/1-component/DRI-row (inferred) payloads=27/27 identical PSNR=infdB
color-gray_2page_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=46/54 identical PSNR=76.72dB
color_a4_media-env.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=23/27 identical PSNR=81.64dB
color_a4_media-heavy.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=27/27 identical PSNR=infdB
color_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=23/27 identical PSNR=81.64dB
color_a4_media-light_quality-best.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=23/27 identical PSNR=81.64dB
color_a4_media-light_quality-draft.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=27/27 identical PSNR=infdB
color_a4_media-matte.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=23/27 identical PSNR=81.64dB
color_a4_media-postcard.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=27/27 identical PSNR=infdB
color_a5_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=18/19 identical PSNR=88.72dB
color_lettercustom_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=21/25 identical PSNR=81.48dB
color_letter_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=21/25 identical PSNR=81.48dB
color_mono_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/1-component/DRI-row (inferred) payloads=17/27 identical PSNR=22.28dB
gray_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/YCbCr-422/DRI-row (inferred) payloads=23/27 identical PSNR=74.47dB
gray_mono_a4_media-light.prn: records=IDENTICAL tables=IJG-Q90/1-component/DRI-row (inferred) payloads=17/27 identical PSNR=20.30dB
PASS: all 16 golden streams parsed, decoded and compared; dynamic metadata masked
```

The comparison passing means framing/parse invariants hold, **not pixel identity**.
Mono tonal conversion remains unmatched; Normal/High color differs slightly from
Draft due to omitted OEM enhancement. See [TECHNICAL.md](TECHNICAL.md) for examples and limitations.
The source list is reversed before raster creation, matching GPD
`OutputOrderReversed?: TRUE` and the PPD default. This queue behavior has not
been exercised on macOS. Letter crops extend beyond the source width and use
white, not Pillow's default black padding.

Actual `make test` result after encoder/parser changes:

```text
VALID: 2 pages, 6 bands, 36505 bytes; all records/checksums/JPEG bands verified
ROUNDTRIP gray: 2 pages, 3 bands/page, max-channel MAE=0.232 < 8 PASS
PASS: full/partial bands and row-token boundaries (11 heights)
PASS: 105 paper/media/quality combinations
PASS: PJL metadata injection sanitized
PASS: file/stdin input; empty, truncated, unsupported raster/options/copies rejected
PASS: every binary byte mutation rejected (except legal A4->A5); truncation/trailing/PJL corruption rejected
ALL TESTS PASSED; visual evidence: build/test/comparison.png
```

Viewed `build/test/comparison.png`, `build/golden/band-golden.png`, and
`build/golden/color-golden.png`: RGB/gray synthetic panels align; golden red
ends after row159 and primary color order is red/green/blue. Saved golden crops
are exact pixel crops, not screenshot-derived measurements.

Actual PPD validation:

```text
ppd/Deli-L511W.ppd: PASS
        WARN    Size "LetterCustom" should be the Adobe standard name "Letter".
        WARN    Size "Photo4x6" should be the Adobe standard name "102.28x151.98mm.Fullbleed".
```

The names distinguish the custom on-wire Letter record and preserve the existing
photo option. No macOS package build, real queue or printer test was performed.

## Initial static-reconstruction checks (historical)

Environment: Ubuntu Linux, `cc (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`,
CUPS 2.4.1, system libjpeg-turbo. No Windows execution or printer.

`make` compiled both C programs with `-std=c11 -Wall -Wextra -Wpedantic` and
no compiler diagnostics. `make test` completed successfully. Selected actual
parser/test output:

```text
  band 1: y=0 384x256 payload=12007 checksum=00197c75 OK JPEG decoded
  band 2: y=256 384x256 payload=26345 checksum=0038a99b OK JPEG decoded
  band 3: y=512 384x25 payload=3307 checksum=00072e0b OK JPEG decoded
page 1: A4 media=ff RGB 384x537 bands=3 copies=2 quality=90 OK
VALID: 2 pages, 6 bands, 85066 bytes; all records/checksums/JPEG bands verified
ROUNDTRIP rgb: 2 pages, 3 bands/page, max-channel MAE=2.645 < 8 PASS
  band 1: y=0 384x256 payload=7958 checksum=0011e280 OK JPEG decoded
  band 2: y=256 384x256 payload=7958 checksum=0011e280 OK JPEG decoded
  band 3: y=512 384x25 payload=1313 checksum=0002f061 OK JPEG decoded
page 1: A4 media=ff gray 384x537 bands=3 copies=2 quality=90 OK
VALID: 2 pages, 6 bands, 36207 bytes; all records/checksums/JPEG bands verified
ROUNDTRIP gray: 2 pages, 3 bands/page, max-channel MAE=0.232 < 8 PASS
PASS: full/partial bands and row-token boundaries (11 heights)
PASS: 72 paper/media/quality combinations
PASS: PJL metadata injection sanitized
PASS: file/stdin input; empty, truncated, unsupported raster/options/copies rejected
PASS: every binary byte mutation rejected (except legal A4->A5); truncation/trailing/PJL corruption rejected
ALL TESTS PASSED; visual evidence: build/test/comparison.png
```

**Visual check performed:** viewed `build/test/comparison.png`, containing input
and decoded RGB/gray panels. Primary/secondary bars, gradient directions, grid
lines and full/partial-band boundaries align; no visible color swaps, missing
rows, or band discontinuities. Small lossy-JPEG differences are expected.
Generated PRNs/PNGs/full log remain under ignored `build/test/` and can be
regenerated with `make test`; they are not vendor golden fixtures.

```text
$ cupstestppd -I filters ppd/Deli-L511W.ppd
ppd/Deli-L511W.ppd: PASS
        WARN    Size "Photo4x6" should be the Adobe standard name "102.28x151.98mm.Fullbleed".
```

The stable user-facing Photo4x6 option deliberately keeps its short name; its
non-exact-4×6 dimensions follow the DLL's borderless R4 mapping.
Filter lookup was skipped because this check is before installation.
`sh -n scripts/build-pkg.sh` exited 0. The pinned JPEG archive SHA256 was fetched
and checked against the value in that script.

During development, libcups rejected padded synthetic scanlines; fixtures now
use valid exact raster strides. A separate probe found a retained libcups input
limitation: a partial next-page header following a complete page is interpreted
as EOF, and the filter returns success for the complete preceding pages. This
is documented in TECHNICAL.md, not covered up by the truncation test (which checks
an initial short header and truncated pixels).

**Not checked here:** macOS compile/universal link/pkgbuild, installed macOS
CUPS absolute-filter lookup, installer execution/signing policy, Windows
byte/table equivalence, status handshake, firmware acceptance or physical print.
The workflow/script are provided but have not run on a Mac in this session.
