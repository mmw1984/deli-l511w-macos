# v2 input/rendering audit

Spooler was Running after restart. All original attachment PNGs are 4960x7016 and match the user's Linux file hashes exactly. Color/band are RGB; gray is L. DPI metadata is 599.9988x599.9988 (PNG pixels/metre rounding).

## Root cause: original intermediate GDI+ copy, not source PNGs

The v1 code loaded `new Bitmap(f)`, allocated a same-size 24bpp bitmap, then used `Graphics.DrawImageUnscaled(src,0,0)`. Despite its name, on this machine that copy did NOT preserve the source pixels with these DPI-tagged images. Reproducing the exact code yielded the following full converted-BGR hashes:

- color: 2ef11e7bf22df98d1bb836add03f9c33f5ff3b8b4c46981a0f12b529f910ca51
- gray: f00fc90c4e27a2552758eb85b2c980f8ca442bad284455b70634f75308d2e2b0
- band: 8e64b8c7c7b8a98a43354d104dbba3241065b5c2299c8ae6ec22eee3fec7abfc

For color, source pixel (100,100) was white but the converted pixel was red. For band, source pixel (100,100) was red but converted pixel was white. This reproduces corruption before GDI printing. Therefore the original claim that DrawImageUnscaled avoided DPI effects was incorrect. The exact internal GDI+ DPI calculation was not instrumented; no precise scale factor is claimed.

The final StretchDIBits call itself used source rect (0,0,4960,7016), destination (-PHYSICALOFFSETX,-PHYSICALOFFSETY,4960,7016), top-down 24bpp DIB, and equal source/destination sizes. Thus it copied already-incorrect intermediate pixels 1:1. On A4 the destination was (-96,-96,4960,7016). v1 had no SetMapMode/viewport/window transforms and relied on the default printer DC MM_TEXT; the old map mode was not runtime-recorded.

## Fix and positive verification

v2 uses `g.PageUnit=GraphicsUnit.Pixel` and `g.DrawImage(src,new Rectangle(0,0,src.Width,src.Height),0,0,src.Width,src.Height,GraphicsUnit.Pixel)`. Both rectangles explicitly use source pixel dimensions. Each printer page explicitly sets MM_TEXT, with no SetViewportExt/SetWindowExt transforms. StretchDIBits dimensions and negative physical offset remain unchanged.

The AuditDrawing.cs utility repeats the exact corrected conversion and hashes every byte of the locked 24bpp DIB. All 3 hashes match Pillow's RGB-to-BGR bytes exactly (stride 14880, no padding). This includes L-mode grayscale, which System.Drawing loads as Format32bppArgb and then correctly converts to 24bpp BGR with equal gray channels. See drawing-audit.txt and input-audit.json. This establishes no scaling, palette changes or misplaced pixels in the submitted DIB, not decoded PRN pixel identity.

The exact requested make_inputs.py ran in C:\work\inputs_v2. New files have different container hashes under Pillow 13.0.0, but all pixel hashes and modes match the original attachments exactly. Both raw pixel hashes and mode+NUL+pixels hashes are recorded, with definitions. All 16 captures use these new files and the original settings/quality blobs.

## Sanity-check limits

Direct Pillow decoding of first color/band payloads failed both as captured and with just SOI/EOI markers restored. No JPEG headers/tables reconstruction was attempted. Thus decoded PRN bar widths and red rows are not measured. DIB-to-source pixel identity is independently verified in full, not inferred from file size.

The provided Pillow rectangle syntax is inclusive: bars from x=200 through x=700 have 501 filled source pixels, not 500. Their first printable x should be 104; the band image source rows 96..255 (160 rows) should appear at printable rows 0..159 after clipping. These are source/geometry predictions, NOT PRN decoder measurements.

The old deliverable is preserved at C:\work\deliverable_v1. Screenshot evidence in the new archive is JPEG (converted from preserved v1 PNGs) so the archive contains exactly three PNG files, all inputs.
