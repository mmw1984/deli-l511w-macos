# Deli L511W Windows print driver: static reverse engineering

## Scope and confidence

No printer and no Windows execution were available. All conclusions below are static observations, not a successful printed job or captured spool. Work excludes scanning/copying. Addresses are preferred VAs in **x64 DELIINKPRNDRV.dll**, image base `0x180000000`, unless explicitly labeled monitor. Ghidra inferred several incorrect `void` return types and indirect-call arguments; use the saved assembly to resolve ambiguities before implementation.

**Key result:** this is a Unidrv OEM renderer generating **PJL + Deli Enhanced PCL XL**, with modified JPEG entropy-coded raster bands. It is not evidence of ordinary PCL XL compatibility: proprietary attributes, JPEG header removal, marker replacement and checksums are present. Conversely, the initial assumption of a completely unrelated print language is too strong.

## Acquisition and reproducibility

Used Microsoft Update Catalog search `DELIL511W887B`, update **49bf907e-4f5c-469d-94a7-9ad1012c2b1b**, version **1.0.1.4**, INF date **03/16/2022**. Direct x64 download:

https://catalog.s.download.windowsupdate.com/c/msdownload/update/driver/drvs/2022/09/7c0dad76-3078-483a-ab85-03d5215f2d43_a40c2efef1ee2e5e32224a3b2147fbdcba43f3de.cab

Saved as `driver64.cab` (307513 bytes), SHA256 `5f285c75eb5217d8bdec35897b1649cc8388088a2bac1879b68cb1d7c55732d2`.
Renderer SHA256 `23ddca8d6491825c29a514b1551cd487f931d6d6a6e09cd7d42ae828c3d9336f`.

`7z x driver64.cab -odriver64 -y` extracted all 10 files. 7z warns of 9760 trailing bytes beyond the CAB, but reports `Everything is Ok` (signed package tail; its signature was not independently cryptographically validated). An initial x86 CAB is preserved as `driver.cab`, extracted under `driver/`; do not accidentally analyze it as x64.

Catalog response and metadata are preserved in `catalog.html`, `catalog-details.html`, `download-dialog*.html`. Catalog DownloadDialog POST parameter was `updateIDs=[{"size":0,"updateID":"49bf907e-4f5c-469d-94a7-9ad1012c2b1b","uidInfo":"49bf907e-4f5c-469d-94a7-9ad1012c2b1b"}]`.

Other attempts:
- https://www.deliprinter.com/down.php failed certificate validation; an explicit insecure retry returned Apache 404. No official-site package obtained.
- https://www.drvsky.com/deli/L511W.htm resolves and identifies the exact hardware ID and `http://down.drvsky.com/deli/Deli_InkPrinter_1.0.1.4.exe`; HTTPS download returned 403 and HTTP did not yield an installer.
- qddshi page saved as `qddshi.html`; its official link returned an obfuscated script, not a driver. Did not execute it.
- Catalog name-only search and version 1.0.2.4 query did not yield usable version results in this run. **1.0.2.4 not obtained or compared.** Treexy/drvhub not needed once the exact-ID Microsoft package was found.

## Installed file inventory and architecture

INF is ASCII, not UTF-16. `driver64/DELIINKPRNDRV.inf` maps both XP and Vista+ `Deli L511W` entries to `USBPRINT\DeliL511W887B`.

`[DELIL511W_PAW]`:
```ini
CopyFiles=DELI001DRV,DELI001MON
DataFile=DELIINKATPRNDRV.GPD
LanguageMonitor="DELI INK Language Monitor,DELIINKPRNDRVLM.DLL"
CoreDriverSections="{D20EA372-DD35-4950-9ED8-A6335AFE79F0},UNIDRV.OEM,UNIDRV_DATA,TTFSUB.OEM"
```
Important: **L511W uses INKAT GPD, not INK GPD**, though both install.

Full vendor CopyFiles list (8 files):
- DELIINKPRNDRV.GPD
- DELIINKATPRNDRV.GPD
- DELIINKPRNDRV.INI
- x64/DELIINKPRNDRV.DLL — OEM renderer
- x64/DELIINKPRNUI.DLL — OEM configuration/UI
- x64/DELIINKPRNRS_en-US.DLL — resource library
- x64/DELIINKPRNRS_zh-CN.DLL — resource library
- x64/DELIINKPRNDRVLM.DLL — language monitor

The CAB additionally contains `DELIINKPRNDRV.inf` and `deliinkprndrv.cat` (10 total). OS-provided Unidrv/core resources are referenced through the core dependency, not shipped in this CAB. `[DestinationDirs] DefaultDestDir=66000`, `DELI001MON=66002`.

INI:
```ini
[OEMFiles]
OEMConfigFile1=DELIINKPRNUI.DLL
OEMDriverFile1=DELIINKPRNDRV.DLL
```
Architecture: traditional **v3 Unidrv GPD + COM IPrintOemUni/Uni2 OEM render plugin**, not v4 XPS. Renderer exports only DllCanUnloadNow (RVA ed30) and DllGetClassObject (ed50); RTTI includes `IPrintOemUni2`, `COemUni2`, `COemPDEV`. Imports include WINSPOOL, GDI EngCreatePalette, Kernel32, ole32, Advapi32, Shell32; JPEG implementation is linked statically. PDB path: `C:\Users\shendong\Desktop\PrinterDriver\sources\renderer\x64Release\DELIINKPRNDRV.pdb`.

## GPD capabilities (L511W's INKAT file)

- `ModelName: "Deli InkAT Series"`, PAGE printer, `MasterUnits: PAIR(600,600)`, MaxCopies 1.
- Only declared resolution: Standard 600x600, including TextDPI. Renderer also has explicit 300-dpi branches. No 1200-dpi render setting established; marketing maximum is not a host raster setting.
- Color default 24bpp: DrvBPP 24, ColorPlaneOrder RED/GREEN/BLUE, IPCallbackID 1, DevNumOfPlanes 0. Grayscale DrvBPP 8, callback 3. **These are callback input formats, not CMYK ink planes.**
- All CmdSelect strings and CmdCR/CmdLF/CmdFF/CmdSendBlockData are empty. Stream commands live in the DLL.
- Media: MATTE 260, LIGHT 259 (default), HEAVY 258, ENV 257, POSTCARD 261. Options named by resource IDs, so don't equate every English symbolic name with physical coating without checking resources.
- Quality is implemented in OEM UI/renderer: NORMAL/HIGH/DRAFT. UI strings prohibit draft on photo/inkjet paper and prohibit simultaneous best + image quality optimization.
- Duplex NONE/VERTICAL/HORIZONTAL options exist; this is not proof of an automatic duplex mechanism.
- Paper options: B5, A5, ENV_C5, ENV_DL, HAGAKI_Deli, TAX, A4, seven ATLAS photo/borderless variants, CUSTOMSIZE.
- A4 PageDimensions 4960x7015; PrintableArea 4768x6824; origin 96,96 (600-unit coordinates). Custom limits 60x60 to 5104x7016 in GPD, with a 96-unit margin and 16-unit size rounding. These raw declarations should be preserved rather than assumed physically correct minimum media sizes.

## Rendering path reachability

Not merely unused diagnostic strings: OEMStartPage implementation `18000dc40` checks first-page flag (initialized to 1 in constructor `18000f5a0`), calls EnableSpool `180010ba0`, then job-start `180015820`, session-start `180015430`. OEMNextBand `18000d9b0` calls underlying Unidrv callback, and on end-of-page sentinel (-1,-1) calls page-start `1800147c0`, FlushPrintData `180010e40`, page-end `1800146c0`. OEMEndDoc `18000d920` calls session-end `180015360` and job-end `1800156c0` when error state is zero. WriteSpool `1800174f0` dispatches through the engine callback, or writes its PRN file in the save/replay mode.

This establishes an actual rendering path rather than inferring the protocol from strings. No execution establishes the precise DEVMODE and mode flags chosen for an installed L511W; those remain runtime-unverified. The same package covers many models, but there is no alternate whole-stream renderer observed in these hooks. The GPD/INI bind L511W to this plugin. As a disproof check, inspected model-name gating (`180011ac0`) and the hooks rather than relying on CMYK/PCLXL strings alone: model checks affect paper/image enhancement, while the shared PJL/JPEG path remains in the page hooks.

## Job framing and session bytes

`180015820` emits LF-delimited PJL, beginning `1b 25 2d 31 32 33 34 35 58` (ESC%-12345X), then `@PJL JOB\n`, `@PJL SET STRINGCODESET=UTF8\n`, username/jobname, and vendor controls.

For dmColor=2: `@PJL SET LCOLORMODEL=CMYK\n@PJL SET LINKSET=AUTOMATIC\n`; otherwise BLACK/BLACKONLY. This configures the printer, **not evidence that host data consists of separated CMYK planes**.

Other observed controls: ECONOMODE, FIMPROVE, FGHOST, FDENSITY, PNPQIMPROVE, LSHARPEN, LCTPREFERENCE=IMAGE, PRINTQUALITY=NORMAL/HIGH/DRAFT, LPAGEMODE=NORMAL, LCOLLATION, PAGEPROTECT=OFF, RESOLUTION=300 or 600. Final language lines:
```
@PJL ENTER LANGUAGE=PCLXL\n
) HP-PCL XL;2;1;Comment Copyright(c) 1999 Deli Group\n
```

`180015430` constructs a 51-byte session start (LE integers):
```
d1 <dpi:u16> <dpi:u16> f8 89 c0 00 f8 86 c0 06
f8 8f 41 c0 00 f8 88 c0 01 f8 82 48
c8 c0 14 "Deli Enhanced XL=1.2" f8 81 47
```
The quoted string is exactly 20 bytes, without NUL (memcpy count 0x14). Constants verified directly at 18006c894..18006c8c0, see `constants.txt`.

Session end `180015360`: `49 42`.
Job end `1800156c0`: 44 bytes `ESC%-12345X` + `@PJL EOJ\n` + `@PJL LPORTROTATE\n` + `ESC%-12345X`.
Page end `1800146c0`: `c1 <copies:u16> f8 31 44` (6 bytes).

## Raster: modified JPEG, not ordinary JPEG bands

`FlushPrintData` `180010e40` does the following:
1. Processes RGB/gray page buffer (enhancement functions `180010810`, `180011fc0`), rotates where required.
2. Chooses JPEG quality factor, then splits into **256-row bands**, last band shorter.
3. Calls `18000c100` (`CJpegCtrl::CreateCompressImage` source-log identity), which uses statically linked libjpeg-turbo: copyright string at file offset 6e0c0. Quality passed to jpeg_set_quality-like function `180019820` is factor*100, baseline forced. Gray input = one component; 24bpp = three, input colorspace enum 8 (libjpeg-turbo extended RGB-family ordering must be checked against assembly/buffer production before assuming RGB vs BGR).
4. Default factor 0.9; plain media 0x103 is 0.90 network vs 0.94 local; some other media reset 0.90. Earlier 0.8 initialization is overwritten for final band encoding. Final call to SetCompressOption uses subsampling option 3, whose component sampling setup is 2x1 for component 0 and 1x1 for other components: consistent with 4:2:2. Exact mode-dependent behavior still needs a captured job.
5. Scans the JPEG until `ff da` (SOS); reads its big-endian segment length L, then starts payload at `SOS_pointer + L`. **Not** at SOS+L+2: it overwrites the last two SOS bytes with `ff 2c`. All JPEG tables/frame/header metadata before this point are discarded.
6. Replaces the last payload byte (normally JPEG EOI's d9) with a row-count token. Full 256 rows = d7. Last band token mapping indexed by ceil(rows/8) modulo 8 is `[d7,d0,d1,d2,d3,d4,d5,d6,d7]`; code explicitly handles divisible-by-8 case separately. Thus rows 1..8 => d0, 9..16 => d1, etc., cycling every 64 rows. Reconstructing a standard JPEG requires restoring headers/tables and markers, not feeding this payload straight to a JPEG decoder.

`180013bc0` SendJpegImageBlock computes `checksum = 0xfa + sum(four LE payload-length bytes) + sum(payload bytes)` (32-bit value), calls BeginImage, writes payload, then EndImage. No RLE/PackBits/JBIG/zlib path was identified for this normal raster route. That is not a proof no such routines exist anywhere in the binary.

### 89-byte BeginImage record (`180013de0`)

This byte layout is reconstructed from stores and constant reads, not captured. u16/u32 below are LE. Let W = image width, H = min(256,remaining rows), Y = row offset, D = dpi, N = payload length, S = checksum:
```
c0 cc f8 2c 7b
d3 00 00 <Y:u16> f8 4c 6b
c0 00 f8 64 c0 02 f8 62
c1 <W:u16> f8 6c c1 <H:u16> f8 6b
d1 <W:u16> <H:u16> f8 67
c0 08 f8 fa c0 02 f8 f9 c1 00 00 f8 f8
c1 <D:u16> f8 f7 c1 06 00 f8 f6 b0
c1 00 00 f8 6d c1 <H:u16> f8 63
c0 f6 f8 65 c2 <S:u32> f8 f5 b1
fa <N:u32>
```
The following N bytes are the modified JPEG payload. Vendor attributes include f8 fa/f9/f8/f7/f6/f5; precise semantic names are not yet established. In particular don't mistake c0 02 in a fixed image record for proof of CMYK input.

### 29-byte EndImage record (`180014430`)
```
c1 00 00 f8 6d c1 <H:u16> f8 63 c0 f7 f8 65
c2 aa 00 00 00 f8 f5 b1 fa 01 00 00 00 aa b2
```
Then remaining rows decrease by 256 and Y increases by 256 (or remaining becomes zero for final band). Raw constant at 18006d920 is `fa 01 00 00 00 aa b2`.

## Paper and media encoding

Page-start `1800147c0` maps dmMediaType 0x101->f7, 0x102->dd, 0x103->ff, 0x104->dc, otherwise f6 (includes 0x105 postcard). It emits typed value `c0 <media> f8 27`. Normal quality code from OEM private DEVMODE +0x4e: 1=>NORMAL, 2=>HIGH, else DRAFT (heavy media forces NORMAL).

Standard paper table VA **180068d90**, stride 0x34, 14 entries, dumped in constants.txt. Fields observed: Windows paper ID u16 at +0, dimensions u32 at +4/+8, ASCII name at +12, model mask at +40, border flag byte +44, media/default code +48. IDs/names: 9 A4, 11 A5, 13 JISB5, 88 JISB6, 1 LETTER, 5 LEGAL, 7 EXEC, 14 FOLIO, 20 COM10, 37 MONARCH, 28 C5, 31 C6, 32 C65, 27 DL. These are **not direct one-byte on-wire paper codes**: page-start emits name as `c8 c0 <name-length> <ASCII-name> f8 25`. Custom/photographic sizes use another table/path (`1800118b0`), float dimensions and vendor fields; full page-start layout not yet transcribed. Do not assume table options are all exposed for L511W.

## Network and language monitor

INF installs a **language monitor**, not a standalone custom port-monitor registration. DLL export InitializePrintMonitor2 at monitor VA 180001750 returns table at 180027000. It wraps underlying port callbacks, has Winsock imports and reads `DsSpooler`, `IPAddress`, `IPChgAddr`, SerialNumber.

Monitor assembly at **1800012d9..180001349** creates socket(AF_INET=2, SOCK_STREAM=1, IPPROTO_TCP=6), calls htons(**0x238c = 9100**) at 180001319, inet_pton at 180001333 and connect at 180001349. Monitor's ordinal Winsock imports decode as socket 23, send 19, htons 9, connect 4, closesocket 3. `180001440` sends raw data through ordinal 19 when network mode flag +0xe0 is zero; otherwise delegates underlying WritePort. Thus **raw TCP/9100 is implemented**, with underlying port fallback. Full runtime selection/IP discovery path and bidirectional status handshakes not verified. No evidence here requires IPP or LPD. Do not claim the printer's actual listening services are verified without hardware.

## Saved analysis artifacts / next gaps

- `render.c`, `monitor.c`: whole-binary Ghidra decompilation; `render.asm`, `monitor.asm`: objdump Intel assembly.
- `ghidra-project/`: persistent projects; `DumpAll.java`: decompiler export script; `tools/ghidra_11.0_PUBLIC/`: headless tool. Java17 works with this release. `ghidra-*.log` includes unrelated optional script compilation diagnostics, but DumpAll ran and projects saved.
- `evidence.py` and `constants.txt`: reproducible raw constant/table reads.
- Priority gaps before a CUPS implementation: capture golden Windows PRNs without hardware (FILE: port), establish exact L511W runtime model mask/DEVMODE, fully transcribe page-start and photo/custom paper paths, verify color ordering and JPEG quant/Huffman table reconstruction, identify image attribute semantics/checksum acceptance, test transport/status initialization, compare 1.0.2.4. No hardware output or Windows driver installation was tested.
- Potential path forward is a raster-to-enhanced-XL encoder using JPEG bands, **not** a CMYK plane/halftoning reimplementation at this stage. Firmware appears to receive contone raster; actual ink separation/dithering algorithm remains unknown and may be printer-side. This inference is not hardware-verified.
