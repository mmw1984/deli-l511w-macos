# Deli L511W PNG-to-PRN deliverable

## v2 corrected rendering

Original attachment inputs were correct 4960x7016 files and matched the expected hashes. The v1 intermediate Graphics.DrawImageUnscaled copy did not preserve their pixels; this was reproduced before printing. v2 uses explicit source/destination pixel rectangles and MM_TEXT. All 3 converted 24bpp DIB hashes now exactly match Pillow RGB-to-BGR bytes, including L-mode grayscale. See INPUT_FINDINGS.md, input-audit.json and drawing-audit.txt. v1 is preserved at C:\work\deliverable_v1.

`inputs/` contains the three regenerated 4960x7016 PNGs and the exact make_inputs.py; its duplicate is in src/. Their pixel hashes match originals, although PNG container hashes differ. The manifest includes input metadata/hashes and per-job input SHA256 references and draw geometry. `PRN_sizes_v1_v2.md` compares all 16 captures. `decode-check.json` records unsuccessful direct JPEG-band decode attempts; PRN raster bar measurements are not claimed. Screenshots are retained as JPEGs so exactly three PNG input files are in the ZIP.

Built using the installed .NET Framework 4 C# compiler; no SDK installation needed.

Installed driver: **Deli L511W 1.0.1.4**, INF date 03/16/2022. Microsoft Update Catalog searches by hardware ID, model name and version did not find **1.0.2.4**; no second driver version is included.

## Layout

- `prn/`: 16 golden binary print jobs.
- `tickets/`: per-job PrintTicket XML converted from the validated DEVMODE.
- `devmodes/`: UI-captured default/quality blobs, public fields, full hex and byte diffs.
- `screenshots/`: inspected preference tabs and dialogs.
- `src/`: C# source, build/generation/verification scripts and observed-stream parser.
- `PrintPng.exe`: compiled console tool.
- `manifest.json`: jobs, source paths, settings, public/private DEVMODE, caps, ticket paths, sizes and hashes.
- Root per-job JSON and `.devmode.bin` files: original job records and validated DEVMODEs.
- `NOTES_observed.md`: byte-offset-backed comparison against the supplied static reverse engineering.
- `stream-observations.json`, `first512.hex.txt`, `first-band-context.hex.txt`: reproducible parser evidence.

## Build / run

Run `src\Build.ps1` in PowerShell to rebuild `PrintPng.exe`.

Example (PowerShell):

```powershell
.\PrintPng.exe --printer 'Deli L511W' --images 'C:\image1.png;C:\image2.png' --paper A4 --color color --media LIGHT --devmode 'C:\work\deliverable\devmodes\best.bin' --output 'C:\work\deliverable\prn\example.prn' --job example --ticket 'C:\work\deliverable\tickets\example.xml' --record 'C:\work\deliverable\example.json'
```

Each PNG becomes one page in one StartDoc/EndDoc job. Output must not already exist. Paper accepts A4, A5, Letter, LetterCustom; color accepts color/mono; media accepts LIGHT/MATTE/HEAVY/ENV/POSTCARD. Quality uses a captured full DEVMODE blob. `--dump filename` exports current per-user defaults. PNG pixels are copied with explicit pixel-unit source/destination rectangles onto a white 24bpp bitmap, then transferred as a top-down DIB with identical source/destination dimensions. Each printer page uses explicit MM_TEXT and negative PHYSICALOFFSETX/Y. No fit, centering or DPI-based copy is used. Device DPI must be 600x600; clipping is expected.

`src\Generate.ps1` generated the 16 jobs. Existing job records are skipped; use a fresh output directory to regenerate rather than relying on skip logic to detect changed inputs. `src\Verify.ps1` verifies hashes, lengths, caps and ticket XML, and annotates manifest normalized hashes/PJL quality. `src\VerifyErrors.ps1` exercises empty/error CLI cases.

## UI investigation

Screenshots in screenshots/: layout.jpg, paper-quality.jpg, extension.jpg, defined-paper.jpg, advanced.jpg.

Layout: Orientation; Print on Both Sides; Page Order; Pages per Sheet / Booklet radios; pages-per-sheet count; Draw Borders (disabled for 1-up); preview; Advanced.

Paper/Quality: Paper Source; Media; Black & White / Color radios; Advanced.

Extension (OEM): Quality Draft / Standard / Best radios; Defined paper button. No ink or borderless control was visible.

Defined paper dialog: Name, Width, Length edits; Milimeter radio; custom-paper list; Reset, Confirm, Delete (initially disabled), Save, Close. Advertised limits: width 89.0–210.0mm, length 127.0–297.0mm.

Advanced: Paper Size; Copy Count; ICM Method; ICM Intent; Advanced Printing Features; Pages per Sheet Layout; Booklet Binding Edge; base color mode; OK/Cancel. Preferences also have OK/Cancel/Apply and window Close.

## Private DEVMODE

devmodes/standard.bin is the initial untouched default. Total 1148 bytes: public dmSize=220, private dmDriverExtra=928. Full hex is in standard.bin.hex.txt. Draft and Best were selected in the actual OEM UI and applied before capture. Standard was then reapplied; standard-applied.bin is the normalized comparison baseline and generation default. Queue preferences were restored to Standard.

Compared against standard-applied.bin, only two byte offsets change:

| Absolute offset (decimal) | Private offset | Draft | Standard | Best |
|---|---|---|---|---|
|1112|892|1|2|3|
|1142|922|0|1|2|

The first appears to be the low byte of a 32-bit OEM field. The tool uses full captured blobs rather than assuming a portable layout. DocumentProperties(DM_IN_BUFFER|DM_OUT_BUFFER) validates all changes, then CreateDC receives that per-job DEVMODE. The validated blob and private hex are recorded for every job. PrintTicketConverter converts exactly that validated DEVMODE to a JobScope ticket. Public dmPrintQuality and dmYResolution remain 600 for all three quality choices. The private bytes survive validation; PRN PJL quality is independently inspected by Verify.ps1.

## Findings

Letter (DMPAPER_LETTER=1) is accepted despite its absence from the GPD: physical caps 5100x6600. An additional explicit custom Letter job (256, 2159x2794 tenths-mm) also yields 5100x6600. A4 is 4960x7015 rather than the supplied PNG height 7016; A5 is 3496x4960. A4 physical offsets are 96x96 pixels with printable 4768x6824. The PNGs are not resized for any paper.

Windows reserves the directory name PRN: the requested prn directory was created via the extended-length path `\\?\C:\work\deliverable\prn`; ordinary child-file paths work.

Raw PRNs contain job-name, generated file-ID, and timestamp metadata. The manifest includes both raw hashes and normalized hashes removing only these three PJL lines, so metadata differences are not mistaken for changed print content. Equal sizes alone do not imply equal output.

No physical hardware or raster decoder was available; output-file generation, GDI acceptance, settings, caps, private-byte persistence, ticket XML and PRN headers were checked, not physical print appearance.
