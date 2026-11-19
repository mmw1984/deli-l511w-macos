# Deli L511W Enhanced XL — experimental CUPS driver

**No printer or golden Windows PRN has validated this driver. Do not use for
production printing.** It implements the best current static reconstruction of
Windows x64 renderer 1.0.1.4, not a claim of byte-identical Windows output or
firmware acceptance. `TODO(golden)` comments identify assumptions to revisit.
The reference analysis is `../NOTES.md` (not required to build this repository).
This software is based in part on the work of the Independent JPEG Group.

## Build and hardware-free checks (Linux)

Dependencies on Debian/Ubuntu:

```sh
sudo apt-get install build-essential pkg-config libcups2-dev libcupsimage2-dev libjpeg-dev python3-pil cups-client
make
make test
cupstestppd -I filters ppd/Deli-L511W.ppd
```

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
| `PageSize` | A4, Letter, A5, Photo4x6 | `A4`, `LETTER`, `A5`, OEM `R4` name |
| `ColorModel` | RGB, Gray | PPD chooses RGB24 or W8 raster; PJL CMYK/BLACK |
| `DeliQuality` | Draft, Normal, High | PJL DRAFT/NORMAL/HIGH; photo forces NORMAL for Draft |
| `MediaType` | Auto, Plain, Photo, Matte, Envelope, Postcard | ff/dd/dc/f7/f6; Auto uses photo for R4, plain otherwise |
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

### TODO(golden): must validate before calling this Windows-equivalent

1. Exact runtime L511W model mask/private DEVMODE: particularly color selector,
   R4 borderless entry and media defaults. Letter is present in the DLL table,
   but not exposed in the L511W GPD's limited paper list. Margins for Letter/A5
   use the most likely 96-unit origin; R4 uses zero. A4 uses the GPD geometry.
2. Compare DQT, DHT, SOF and entropy output with Windows. The DLL embeds
   libjpeg-turbo and appears to use IJG defaults and quality 90 for network;
   USB/plain can use 94. We use slow integer DCT, nonoptimized Huffman coding,
   and explicitly 2×1/1×1 sampling. Exact JPEG version/rounding is not proven.
3. Windows passes extended BGR after its own buffer production; the CUPS filter
   passes its RGB input as RGB. The callback boundary/channel swap and optional
   Windows gamma/sharpening/line enhancement are not reproduced or verified.
4. PJL host/file/time metadata uses portable stand-ins, sanitized against command
   injection. Private enhancement defaults are chosen OFF. These will not be
   byte-identical to dynamic Windows job metadata. Quality modes currently change
   PJL only; no unsupported claim of matching OEM image enhancement is made.
5. Row tokens, proprietary attribute semantics, mixed-page handling, firmware
   acceptance, copies, transport/status behavior and physical output still need
   a golden PRN and/or printer. The local parser intentionally validates the
   reconstruction, not these external facts.

Golden captures should include RGB primary bars, grayscale ramps, partial/full
bands, each paper/media/quality, copies, and multi-page jobs. Keep original PRNs
and compare framing/tables before changing assumptions. Hardware-free decode
passing is a useful regression check, **not a substitute for those captures**.
