# Local verification

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
is documented in README, not covered up by the truncation test (which checks
an initial short header and truncated pixels).

**Not checked here:** macOS compile/universal link/pkgbuild, installed macOS
CUPS absolute-filter lookup, installer execution/signing policy, Windows
byte/table equivalence, status handshake, firmware acceptance or physical print.
The workflow/script are provided but have not run on a Mac in this session.
