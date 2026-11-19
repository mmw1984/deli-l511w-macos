# Antialiasing / JPEG study

## Recommendation

Keep **Smooth** as the default. Offer **HighQuality / 高質平滑** as an experimental
4x supersampled, box-downsampled alternative on macOS and Android. Do not promote
it to the default or tag v0.2.2 from this synthetic experiment alone.

The 4x area candidates are closest to this reference. Edge-only gamma improves
edge PSNR by just 0.047 dB over plain 4x box, without an obvious visual advantage;
avoid its tonal changes. Lanczos/unsharp do not beat plain 4x box, and Mitchell
loses fine-edge contrast. The zoom comparison shows much smoother diagonal lines
and glyph curves than aliased rendering; 4x box and gamma look very similar.

This does **not** establish that HighQuality beats native CoreGraphics Smooth.
Smooth already computes coverage analytically; 2x/4x Pillow approximations are
not measurements of its actual algorithm. Likewise, FreeType hinting changes
with scale, and an 8x box reference favors area-like filters. There is no physical
printer, ink-spread or optical comparison here. Native and real-printer A/B tests
remain necessary before changing the default. Colored JPEG fringes remain: no
sampling/tables/protocol changes are made.

## Reproduction

On Linux, with the normal build dependencies, Pillow and the system
`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` font:

```sh
python3 tools/aa_study.py
```

`tools/aa_study.py` draws black/red/blue text and 0.35–2 pixel diagonal lines.
The aliased candidate uses a binary FreeType font mask while preserving ink
colors. Supersampled candidates use the **same portable `src/resample.c`** used
by the drivers, at 2x and 4x, with box, Lanczos-3 and Mitchell (B=C=1/3) kernels.
Gamma is `255*(value/255)^1.1`, restricted to a local-contrast edge mask; unsharp
is Pillow radius 0.5, amount 30%, threshold 2. Every candidate goes through
`raw_raster` → `rastertodeli` (Q90, 4:2:2) → `tools/parse_deli.py` → decoded RGB.
JPEG/framing/mono calibration are unchanged.

The reference is an uncompressed 8x render reduced by area averaging to 600 dpi.
PSNR is computed on decoded RGB against that reference. Edge PSNR uses reference
3x3 local-luminance range >12. White MAE is decoded luminance error on reference
white pixels whose 7x7 neighborhood is also white (0–255 units; lower is better).

Outputs are ignored build evidence, not tracked captures:

- `build/aa-study/compare.png`: side-by-side nearest-neighbor 2x zooms.
- `build/aa-study/metrics.json`: full-precision measurements.
- `*-input.png`, `*.prn`, `*-decoded.png`: each pipeline stage.

## Decoded-output results

| Candidate | PSNR dB | Edge PSNR dB | White MAE |
|---|---:|---:|---:|
| Aliased | 20.908 | 9.641 | 0.0457 |
| 2x box | 28.040 | 16.790 | 0.0475 |
| 2x box + edge gamma | 28.006 | 16.756 | 0.0478 |
| 2x Lanczos-3 | 28.488 | 17.256 | 0.0521 |
| 2x Mitchell | 28.554 | 17.304 | 0.0464 |
| 4x box | 34.907 | 23.768 | 0.0493 |
| 4x box + edge gamma | 34.950 | 23.815 | 0.0490 |
| 4x Lanczos-3 | 34.675 | 23.586 | 0.0517 |
| 4x Lanczos-3 + unsharp | 34.680 | 23.597 | 0.0520 |
| 4x Mitchell | 33.654 | 22.468 | 0.0474 |
| 4x Mitchell + unsharp | 34.278 | 23.112 | 0.0476 |

## Implementation and checks

HighQuality renders 2400 dpi into 32-output-row tiles (128 source rows), then
averages exact 4x4 areas to 600 dpi. Eight tiles make an ordinary 256-row encoder
band. A4's source bitmap is 9.8 MB rather than a roughly 2 GB full-page bitmap;
Android also uses pixel arrays and may incur JNI copies. Memory is bounded by
width and strip height, not page height. Box averaging has no cross-output-pixel
support, so no halo rows are needed. The experimental wider kernels are measured
by the study but are not exposed in either driver.

`make test` includes portable 2x/4x kernel tests: exact box averages, constant
images, invalid/empty input, and tiled/full equivalence with three-output-row
halos (sufficient for Lanczos-3). On macOS it also compiles/runs the actual
CoreGraphics filter: all three modes, geometry and band-crossing solid fill,
HighQuality blank PDF, malformed input, and black/red text plus thin lines.
Both the main package workflow and release workflow run these native tests;
the main workflow saves `PDF-render-tests` PNG artifacts.

Android instrumentation checks JNI color ordering, empty/invalid arrays,
HighQuality-vs-Smooth differences and **pixel-exact** tiled-vs-full rendering
across both 32-row and 256-row boundaries. Existing planner/persistence and
system-print-dialog → JNI → silent TCP fake-printer tests also run. These are
software checks, not physical acceptance tests. Android's Crisp and Smooth
remain identical PdfRenderer print-mode rendering; only HighQuality supersamples.
