# Deli L511W — technical reference

**Windows v1.0.1.4 golden framing is validated; a user reports successful
hardware printing. The new PDF rendering and manual-duplex paths still need
Mac/printer validation.** Color payloads mostly match exactly;
monochrome uses an empirically calibrated Windows tone curve. This is not a claim of
byte-identical Windows output or firmware acceptance.
Commands below run from the repository root. The original external analysis
is `../NOTES.md` relative to that root (not required to build this repository).
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

Both filters follow CUPS arguments (`job-id user title copies options [file]`),
or their respective input on stdin. Diagnostics go to stderr only.
The raster filter rejects non-600dpi,
planar, non-8-bit, non-RGB/W, zero-size and duplex raster headers, truncated
pixel input, unknown exposed options, and mixed RGB/gray pages within one job. Memory
uses one 256-row band plus a row and compressed JPEG, and a temporary disk cache
of all input pages for selection/reordering; dimensions are 16-bit wire values.
Empty input is an error; a valid document with an empty page selection produces
no job. A failed/cancelled job may have
already emitted a partial stream and must not be sent/retried as a complete job.
Known input limitation: libcups reports EOF and a short page header identically;
a trailing partial page header after complete pages can be treated as end-of-job.
The filter does not implement a second raw CUPS framing parser to disambiguate
that case. The output parser does reject all truncated output records.

## 清晰文字、黑白及手動雙面（macOS）

重新安裝套件後，請刪除舊佇列再用新 PPD 加回印表機，避免 macOS 沿用舊選項。
新 PPD 優先用 `pdftodeli` 直接接收 PDF；`rastertodeli` 仍可處理 CUPS raster。

### 文字清晰度 / Rendering

預設及建議 **Smooth（平滑）**：CoreGraphics 以 600 dpi 畫 PDF，開啟反鋸齒，
但不開啟子像素字型平滑。**Crisp（不建議）**關閉反鋸齒，實機回報鋸齒及雜訊反而較明顯。
實驗性 **HighQuality（高質平滑）**以 2400 dpi 畫小條帶，再用共享 C 的 4×4 面積平均縮至
600 dpi；保留原有 JPEG 參數。合成測試不能證明優於原生 Smooth，故不改預設；見 [AA study](AA-STUDY.md)。
如果原始 PDF 本身只有低解像度掃描圖，超採樣無法補回不存在的細節。
Rendering 選項只影響直接 PDF 路徑，不能去除已經在 raster 內的灰階邊緣。

PDF 同尺寸頁面按實際紙張大小畫，裁出與 Windows golden 相同的可列印範圍：
A4 4768×6824、Letter 4896×6400、A5 3312×4768，左／頂偏移 96 px。
Photo4x6 為 2416×3590、無邊框。其他 PDF 頁面尺寸會等比例縮放、置中至可列印範圍，
橫向頁面自動旋轉至適合所選紙張；保留 PDF 自帶旋轉及裁切框。
內部用每分量 8-bit、32-bit RGBX bitmap（CoreGraphics 支援的格式），送編碼器前轉 RGB24。
輸出每帶 256 行；HighQuality 每次只畫 32 個輸出行（128 個高解像行，A4 約 9.8 MB RGBX），
再拼回編碼帶，無須全頁 2400 dpi bitmap。面積濾波無跨輸出行支援，故不需額外邊界行。
stdin PDF 及 raster 暫存使用安全臨時檔；raster 會先數完頁數。

仍然使用 **Q90、4:2:2 JPEG**：彩色細字（尤其紅／藍字）可能受色度水平降採樣影響。
golden 的 JPEG 頭／取樣因子已被剝除，現有記錄沒有已證實的取樣切換欄位；不能只改成
4:4:4，否則印表機可能用錯解碼參數。黑白模式不含色度平面，適合純文字文件。

### 黑白 Black & White

在 macOS 內建 **Black & White／黑白** 方格打勾，或在 Color Mode 選 **Grayscale**。
新 PPD 亦包含「黑白 Black & White」、「彩色 Color」的 Apple preset（是否顯示 preset
取決於應用程式；部分 App 只在相片列印樣式顯示 APPrinterPreset）。繁體中文標籤使用
`zh_TW` PPD 本地化；英文介面顯示英文名稱。

PPD 保留標準 **ColorModel Gray** 選項；它故意仍要求 RGB24 raster，避免系統預先丟失
色彩資訊。兩個 filter 都先套用同一 Windows 校準 LUT，再作 BT.601 RGB→灰階。
直接 `print-color-mode=monochrome` 同樣有效。CUPS 2.4.1
[`cups/ppd-cache.c`](https://github.com/OpenPrinting/cups/blob/v2.4.1/cups/ppd-cache.c)
的 `_ppdCacheCreateWithPPD` 明確找 `ColorModel` 的 **Gray** choice（約第1555行），並把它
加入 monochrome presets；不要把 choice 只改名成 Grayscale 或 Mono。Apple extension 格式見
[APPrinterPreset](https://apple.github.io/cups/doc/spec-ppd.html#APPrinterPreset)。
原生方格實際顯示仍須在 Mac 上確認，並非 Linux 能驗證的 UI 行為。

### 手動雙面 Manual Duplex

先用 **4頁及5頁、每頁有大頁碼／頂端箭嘴** 的測試文件試一次；先用一份，不要用正式文件。
兩次都列印**同一份完整 PDF**，同樣紙張／縮放／頁面範圍／輸出次序。不要在 App 再選
「只印單數／雙數頁」或先刪走某些 PDF 頁面，否則 filter 不能知道原來頁碼。

1. 選 **手動雙面 → 第1步 單數頁**，列印並等所有紙張完全輸出。
2. 保持整疊紙的相對次序，不要逐張重新排序。把整疊紙**左右翻面**（直向長邊翻頁），
   放回入紙匣，讓空白面是下一次要印的面。進紙方向要讓背面頂端與正面相符；先以箭嘴
   測試確認。本專案沒有實測 L511W 的紙匣朝上／朝下及先入哪一邊，不能保證一個通用方向。
3. 選 **第2步 雙數頁**、**第2步次序 Auto**，再印同一份完整 PDF。
   亦可用「手動雙面 第1步／第2步」presets。

**Auto 的次序假設與奇數頁：** Windows GPD 要求 Reverse，據此推斷是反序輸出後頁1在疊頂。
預設5頁文件，第1次送 `5,3,1`；整疊翻面後應先餵入頁5那張，再頁3，再頁1。
所以第2次送 **空白,4,2**，而不是直接 `4,2`：空白背面讓頁5那張通過，才不會整疊錯位。
4頁則第1次 `3,1`、第2次 `4,2`。這個推導假設重新放紙後由最後一張單數頁開始進紙；
**輸出反序並不能單獨證明紙匣的進紙順序**，因此務必先測試。

如果背面配到另一端的紙，將 **第2步次序** 改 **Normal** 再測試；它會送 `2,4,空白`
（5頁例）。**Reverse** 明確指定 `空白,4,2`。若只是背面倒轉，應改放紙方向而不是頁序。
Auto 跟隨第1次所選的輸出次序；若兩次皆明確用 `outputorder=normal`，Auto 也會用順序。
`page-ranges`／`page-set` 先選原文件頁碼，再分正背面；如只選到某一面的頁，另一面會補空白
以保留紙張配對。多份 copies 是逐頁硬件複印（不作整份分頁）；建議手動雙面先每次只印一份。

命令列例子（同一 PDF、兩個分開工作；第2次之前先放回紙張）：

```sh
lp -d DeliL511W -o ColorModel=Gray -o DeliDuplex=Odd document.pdf
lp -d DeliL511W -o ColorModel=Gray -o DeliDuplex=Even -o DeliPass2Order=Auto document.pdf
```

直接 PDF filter 自行處理選頁及 Reverse，避免經其他 PDF rasterizer 再處理一次。
raster fallback 的頁碼是**收到的 raster 頁序**；若上游已選頁／倒序，無法從 raster 還原
原 PDF 頁碼。使用 fallback 做手動雙面時，須讓上游交付完整、未倒序的文件，例如兩次皆用
`outputorder=normal`，不要同時由上游套用 odd/even。優先使用新 PPD 的直接 PDF 路徑。

Portable 測試：`build/test_page_plan` 覆蓋1–7頁、兩次列印、三種次序、範圍／奇偶／空白對位；
`make test` 也會實際產生及解碼兩次的 raster stream。新的 PDF 路徑、UI 及翻紙方向目前
**未在 Mac／實機驗證**，請用上述測試頁確認後才用於正式文件。

## macOS universal installer

The package now installs **pdftodeli** (preferred PDF route, cost 0) and
**rastertodeli** (CUPS raster fallback, cost 100). On Darwin, `make` builds both;
Linux builds only the raster frontend, shared encoder, and portable page tests.

Requires Xcode Command Line Tools, `cmake`, and network access to GitHub:

```sh
sh scripts/build-pkg.sh
```

The script verifies a pinned SHA256 archive of libjpeg-turbo 3.0.4, builds its
static library separately for arm64 and x86_64 (SIMD disabled for reproducible
cross-builds), links Apple's SDK libcups, combines with `lipo`, ad-hoc signs the
filters, and runs `pkgbuild`. Minimum deployment target: macOS 11. No Homebrew
CUPS/JPEG dynamic libraries are required on the target Mac. The package contains
libjpeg-turbo's statically linked code; its license/attribution is included in
the installed support directory. The GitHub Actions workflow runs this on
`macos-latest` and uploads the packages from `dist/`. PRs, pushes and manual
dispatch retain the build workflow. Pushing a `v*` tag also runs the release
workflow: native `make test`, universal package build, architecture/signature
checks, then GitHub Release publication with the built-in `GITHUB_TOKEN`.
The tag without its leading `v` becomes the package version (for example,
`v1.2.3` produces version `1.2.3`). Local builds default to `0.1.0`, or accept
`VERSION=1.2.3 sh scripts/build-pkg.sh`. Each build emits both a versioned
package and the identical stable asset **`Deli-L511W-universal.pkg`** used by
the README download link. No release is published if tests or packaging fail.

Install on a test Mac:

```sh
sudo installer -pkg dist/Deli-L511W-0.1.0-universal.pkg -target /
sudo lpadmin -p DeliL511W -E -v socket://192.0.2.10:9100 \
  -P /Library/Printers/PPDs/Contents/Resources/Deli-L511W.ppd
lp -d DeliL511W -o PageSize=A4 -o ColorModel=RGB -o DeliQuality=Normal test.pdf
```

Replace `192.0.2.10` with the printer's stable IP. The language-monitor
[transport audit](LANGUAGE-MONITOR.md) establishes unchanged print bytes and no
TCP application handshake in the LM. Raw TCP/9100 is appropriate; no hardware
has verified listening services or printer acceptance. Windows also performs
UDP/9300 identity/address recovery, which this driver does not reproduce.
Use a DHCP reservation or update the URI if the printer's address changes.
If the printer holds TCP open after jobs, `socket://IP:9100/?waiteof=false`
avoids CUPS waiting for EOF; the LM requires no final response.
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
