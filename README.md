# Deli L511W Enhanced XL — experimental CUPS driver

**Windows v1.0.1.4 golden framing is validated; no printer has been tested.
Do not use for production printing.** Color payloads mostly match exactly;
monochrome uses an empirically calibrated Windows tone curve. This is not a claim of
byte-identical Windows output or firmware acceptance.
The reference analysis is `../NOTES.md` (not required to build this repository).
This software is based in part on the work of the Independent JPEG Group.

## Build and hardware-free checks (Linux)

Dependencies on Debian/Ubuntu:

```sh
sudo apt-get install build-essential pkg-config libcups2-dev libcupsimage2-dev libjpeg-dev python3-pil cups-client
make
make test
make compare-golden
cupstestppd -I filters ppd/Deli-L511W.ppd
```

For native macOS checks, install Xcode Command Line Tools and run:

```sh
brew install pkgconf jpeg-turbo cmake
mkdir -p build
python3 -m venv build/venv
. build/venv/bin/activate
python3 -m pip install Pillow
make test
make compare-golden
```

The native test build uses Homebrew JPEG; the universal installer below instead
links its own static JPEG library and only system dynamic libraries.

`make test` uses the small C raster generator to create
600dpi RGB24/white-based grayscale8 CUPS rasters. Synthetic pages are 384×537
pixels (deliberately smaller than the declared A4 sheet for fast tests), two
pages per job, including full 256-row bands and a 25-row final band. It also
checks row-token boundaries, all paper/media/quality options, malformed input,
PJL injection and bytewise corruption of the binary stream. JPEG is lossy;
the test enforces max-channel mean absolute pixel error <8/255, not identity.
The uninstalled source PPD check skips filter-file lookup; package validation
uses the staged installation root and does check the installed filter path.

To generate and decode a stream manually:

```sh
mkdir -p build/test
build/make_raster rgb 537 1 build/test/input.ppm > build/test/input.ras
build/rastertodeli 1 "$USER" 'Color bars' 1 'PageSize=A4 DeliQuality=Normal' \
  build/test/input.ras > build/test/page.prn
python3 tools/parse_deli.py build/test/page.prn --output build/test/page
```

The strict Python/Pillow parser walks PJL, session, page setup, every BeginImage,
payload checksum, EndImage, EndPage, EndSession and footer; rejects missing,
inconsistent, unknown or trailing records; restores JPEG headers/markers and
assembles PNGs. It accepts **our reconstructed subset**, not every possible
Windows job. Header reconstruction uses Pillow's standard IJG tables, separate
from the C encoder; self-roundtrip is not independent protocol validation.
`build/test/comparison.png` shows RGB input/decoded and gray input/decoded.

The filter follows CUPS arguments (`job-id user title copies options [file]`),
or raster on stdin. Diagnostics go to stderr only. It rejects non-600dpi,
planar, non-8-bit, non-RGB/W, zero-size and duplex raster headers, truncated
pixel input, unknown exposed options, and mixed RGB/gray pages within one job. Memory
is bounded to one 256-row band plus a row and compressed JPEG; dimensions are
16-bit wire values. Empty input is an error. A failed/cancelled job may have
already emitted a partial stream and must not be sent/retried as a complete job.
Known input limitation: libcups reports EOF and a short page header identically;
a trailing partial page header after complete pages can be treated as end-of-job.
The filter does not implement a second raw CUPS framing parser to disambiguate
that case. The output parser does reject all truncated output records.

## macOS universal installer

Requires Xcode Command Line Tools, `cmake`, and network access to GitHub:

```sh
sh scripts/build-pkg.sh
```

The script verifies a pinned SHA256 archive of libjpeg-turbo 3.0.4, builds its
static library separately for arm64 and x86_64 (SIMD disabled for reproducible
cross-builds), links Apple's SDK libcups, combines with `lipo`, ad-hoc signs the
filter, and runs `pkgbuild`. Minimum deployment target: macOS 11. No Homebrew
CUPS/JPEG dynamic libraries are required on the target Mac. The package contains
libjpeg-turbo's statically linked code; its license/attribution is included in
the installed support directory. The GitHub Actions workflow runs this on
`macos-latest` and uploads `dist/Deli-L511W-0.1.0-universal.pkg`.

Install on a test Mac:

```sh
sudo installer -pkg dist/Deli-L511W-0.1.0-universal.pkg -target /
sudo lpadmin -p DeliL511W -E -v socket://192.0.2.10:9100 \
  -P /Library/Printers/PPDs/Contents/Resources/Deli-L511W.ppd
lp -d DeliL511W -o PageSize=A4 -o ColorModel=RGB -o DeliQuality=Normal test.pdf
```

Replace `192.0.2.10` with the printer's IP. The monitor DLL implements raw TCP
9100; no hardware has verified listening services or handshake requirements.
Only send test jobs to your own printer after reviewing this experimental status.
No discovery, ink/status monitor, scan support, or custom backend is provided;
the standard CUPS `socket` backend transports the stream. IPP/AirPrint is not
assumed. PPD/CUPS 2.x compatibility is required; this is not a driverless IPP app.

Installed paths:

- `/Library/Printers/Deli/filter/rastertodeli`
- `/Library/Printers/PPDs/Contents/Resources/Deli-L511W.ppd`
- `/Library/Printers/Deli/libjpeg-turbo-LICENSE.md`
- `/Library/Printers/Deli/libjpeg-turbo-README.ijg`

The source PPD contains the requested relative `rastertodeli` cupsFilter2 entry.
The package rewrites **only its installed copy** to the absolute filter path,
avoiding SIP-protected `/usr/libexec/cups/filter`. The installer is unsigned and
not notarized; the executable is only ad-hoc signed. Distribution signing and
macOS runtime/queue verification remain separate release work. For a native
unpackaged macOS build, use `make CUPS_LIBS=-lcups` and set `JPEG_CFLAGS` and
`JPEG_LIBS` to a matching local libjpeg installation.

On Linux, install the binary into your CUPS serverbin filter directory (usually
`/usr/lib/cups/filter/rastertodeli`) with owner root and mode 755, and use the
source PPD in `lpadmin -P`. Do not place filters in a user-writable server path.

## Implemented options and reconstruction limits

| CUPS option | Values | On-wire reconstruction |
|---|---|---|
| `PageSize` | A4, Letter, LetterCustom, A5, Photo4x6 | standard names, custom Letter float pair, OEM `R4` |
| `ColorModel` | RGB, Gray (also Mono/gray/mono filter aliases) | RGB24 raster; filter converts mono after channel LUT; PJL CMYK/BLACK |
| `DeliQuality` | Draft, Normal, High | PJL DRAFT/NORMAL/HIGH; photo forces NORMAL for Draft |
| `MediaType` | Auto, Plain, Heavy, Photo, Matte, Envelope, Postcard | ff/dd/dc/f7/f6; Photo aliases Heavy; Auto uses photo for R4, plain otherwise |
| copies | 1..65535 | page setup and EndPage LE16 copy count |

The options string selects media/quality; color is taken from the actual raster
header, not an untrusted option label. Supported raster sheet dimensions can
also select paper when `PageSize` is absent. No custom sizes, landscape-specific
rotation, duplex, borderless sizes beyond R4, or color management is implemented.
Let CUPS rasterize orientation, and avoid unsupported job options.

Evidence implemented from renderer VAs (image base `0x180000000`):

- `180015820`: PJL job fields; `180015430`: 51-byte session, 600×600 and the
  exact non-NUL 20-byte `Deli Enhanced XL=1.2` identifier.
- `1800147c0`: simplex page setup, media mappings, paper-name attributes,
  floating identity scale, border selector, 96-unit normal origin, vendor JPEG
  quality attribute. A4/Letter/A5 standard table; R4 OEM table `180069070`.
- `18000c100` / `180010e40`: baseline JPEG at quality 90 (raw-network default),
  standard IJG quant/Huffman tables, 4:2:2 color sampling, 256-row bands.
  Discard through SOS length boundary minus two bytes, overwrite with `ff 2c`,
  replace trailing `d9` with token indexed by `ceil(rows/8) % 8` in
  `[d7,d0,d1,d2,d3,d4,d5,d6]`. Grayscale uses one component.
- `180013de0`: 89-byte BeginImage; checksum is `0xfa + sum(LE32(length)) +
  sum(payload)` modulo 2^32. `180014430`: 29-byte EndImage including the
  one-byte `aa` embedded payload and vendor `aa` field (not the JPEG checksum).
- `1800146c0`: EndPage; `180015360`: `49 42`; `1800156c0`: 44-byte PJL footer.

### Windows golden findings and remaining limitations

`tests/golden/` contains the unmodified v2 capture archive plus the original
PNGs. `make compare-golden` checks capture SHA256 and native-mode source pixel
hashes, creates white-backed printable-area crops, writes actual CUPS rasters,
runs the filter for all 16 manifest jobs, strictly parses both outputs, and
compares framing and decoded pixels. Only file-ID/timestamp are masked in PJL;
the harness supplies the captured username, title and hostname. JPEG-dependent
checksum/length fields are excluded from the non-image comparison and validated
independently for both streams. Payload identity counts and whole-job PSNR are
reported without hiding differing bands. Artifacts are in `build/golden/`.

- JPEG is standard quality-90 IJG DQT/DHT, baseline YCbCr 4:2:2 for color or
  single-component gray for mono, with **one MCU row per restart interval**.
  RGB input needs no channel swap. Exact band payload matches (including the
  red 160-row first band) support these settings. Original JPEG headers/tables
  are stripped from PRNs, so their identity is inferred from entropy equality,
  not directly observable. The decoder inserts the matching DRI segment.
- Draft uses the same tables/resolution as Normal/High. Draft, Heavy and
  Postcard color payloads match the raw source encoder exactly. Normal/High
  differ slightly in the first four color bands: the OEM's non-Draft line
  enhancement is not implemented. The comparison reports its pixel error.
- Mono is one-component JPEG, not color JPEG with BLACK PJL. `tools/derive_mono.py`
  recovers a 256-entry LUT from median decoded gray-ramp samples, with flat
  black/white anchors and linear interpolation for the seven levels clipped out
  of the printable ramp (1–3 and 251–254). It is monotonic, maximum step 5,
  maximum second difference 3; its toe near level16 and shoulder near224 are
  measured features, not smoothed away. Gray128 maps to189.
  Pure color bars disprove applying the LUT after luminance: that predicts
  red139 instead of the observed76. The filter applies LUTs to each RGB channel,
  then rounds BT.601 luminance with integer weights 19595/38470/7471 over65536.
  Those weights and decimal 0.299/0.587/0.114 both exactly fit all eight bars;
  these captures cannot discriminate their rounding for arbitrary mixed colors.
  The PPD preserves RGB channels in Gray mode so CUPS does not prematurely
  convert them. Already-gray W8 input goes through the LUT directly. The golden
  comparison now enforces at least45dB for every mono job. This empirical model
  is validated against these inputs, not an independently recovered Windows
  color-management implementation.
- GPD `OutputOrderReversed?: TRUE` explains the two-page capture's gray-then-
  color order despite the manifest's color-then-gray input list. The PPD
  requests reverse order; the harness supplies raster pages in that CUPS order.
  The filter itself streams pages in received order. Actual CUPS queue page
  reversal on macOS remains untested.
- Origin 96 pixels = 96/600 inch = **4.064 mm = 11.52 points**, exactly.
  Imageable boxes preserve the observed integer-pixel printable extents:
  A4 4768×6824 on 4960×7015, A5 3312×4768 on 3496×4960,
  Letter 4896×6400 on 5100×6600. Opposite margins consequently need not
  equal 96 pixels. LetterCustom uses the captured custom float-pair record.
  R4/photo remains a static reconstruction without a supplied golden.
- Setup copies use private attribute `ec`; EndPage copies use `31`. Mono's
  page color selector is also 2. Media bytes are ff/dc/dd/f7/f6 for
  Light/Matte/Heavy/Envelope/Postcard, with no PJL media setting.
- FDATETIME is local days since 1900-01-01 plus an unpadded decimal decisecond
  count since midnight (renderer assembly 18001614a–1800161e9). File IDs use
  Windows FILETIME tick format; exact Windows job-ID allocation was not derived.
  These dynamic fields are intentionally masked, not copied from captures.

Printer acceptance, copies beyond the synthetic tests, transport/status,
physical margins/output, and macOS packaging still require external validation.
