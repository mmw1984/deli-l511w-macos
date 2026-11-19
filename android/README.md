# Android PrintService

Android 8.0/API 26 or later; target API 35. Manual IPv4 printers, TCP 9100.
No UDP scanning, printer-status query, or firmware delivery acknowledgement.
System “completed” means bytes were sent, not that paper physically printed.

## Build

Install JDK 17 and Android SDK command-line tools; accept SDK licences and install:

```sh
sdkmanager 'platforms;android-35' 'build-tools;35.0.0' 'ndk;27.2.12479018' 'cmake;3.22.1' 'platform-tools'
export ANDROID_HOME=/path/to/android-sdk
cd android
./gradlew assembleDebug assembleRelease
```

Outputs: `app/build/outputs/apk/debug/app-debug.apk` (debug-signed/installable) and
`app/build/outputs/apk/release/app-release-unsigned.apk` (must sign before installing).
No production signing key is included. Debug APKs are for testing; release
distribution needs an owner's persistent signing key and APK upload to Releases.

## Use

Install the debug APK, open **Deli L511W Print**, add a printer name and IPv4
address, then enable the service using the app's system-print-settings button.
Keep printer and phone on the same reachable LAN; reserve its IP in DHCP.
In any app's system Print dialog choose the printer, paper size and color mode.
**More options** exposes media, quality, manual duplex, pass-2 order and rendering.

For manual duplex use the same complete PDF, one copy, all pages, both times:
Odd first, flip/reload the whole stack without reordering, then Even. Auto sends
`5,3,1` then `blank,4,2` for five pages. If backs pair incorrectly try Normal
(`2,4,blank`) or Reverse; if upside down change feed orientation. Test 4/5 numbered
pages first: hardware reload direction remains unverified. Copies are hardware
per-page copies, not collated sets.

## Rendering and native code

PdfRenderer uses **RENDER_MODE_FOR_PRINT**, opaque white ARGB_8888 strips at
600 dpi, 256 rows per band (including the final partial band), with a matrix
offset rather than allocating a full A4 bitmap. Matched paper sizes crop at
96 px; other sizes fit/center and rotate landscape pages. RGB conversion and
JPEG buffers are strip-sized too. PDF and encoded output are cached to private
disk files and removed after success, failure or cancellation. Failed/cancelled
network transmission can leave a partial job at the printer; do not blindly retry.

Android PdfRenderer offers no public antialias switch on minSdk 26.
**Crisp and Smooth currently use the same print rendering**, with no thresholding.
The advanced-options UI explicitly says so. Source scans/colored text may remain
soft. Photo4x6 uses the reconstructed R4 geometry, not a physical acceptance test.

Smooth remains the default. The experimental **HighQuality / 高質平滑** option
renders at 2400 dpi in 32-output-row tiles, then uses `src/resample.c` through JNI
for exact 4×4 area averaging to 600 dpi. Tiles assemble into the same 256-row JPEG
bands. The box kernel needs no halo rows and does not introduce sharpening or
gamma changes. A4's temporary high-resolution bitmap is about 9.8 MB, plus Java
pixel arrays and possible JNI copies; memory does not scale with page height.
Instrumentation compares all tiled pixels with a full supersampled reference
and checks blank/invalid JNI input. See [AA study](../docs/AA-STUDY.md) for limits.

`cpp/bridge.c` includes the existing `src/deli.c` with `DELI_EMBEDDED`; CUPS-only
options are omitted, while PJL, framing, mono LUT, JPEG and geometry are shared.
The only shared-source changes are conditional output/error hooks and Android's
API-26-compatible clock call. JNI owns a duplicated output fd, validates band
geometry/state and converts errors to IOException (never exits the app).
The Kotlin worker serializes print jobs; native fd/error state is thread-local.
`src/page_plan.c` is reused directly. Pinned libjpeg-turbo **3.0.4**, verified by
SHA256, builds as its own CMake ExternalProject for each ABI, SIMD disabled.
Encoding remains IJG Q90, ISLOW DCT, fixed tables, no optimized Huffman, 4:2:2
color/one-component mono, and one MCU-row restart interval.

Cancellation closes an active socket; connect timeout is 8 seconds and the
overall transfer deadline is 120 seconds. Offline manually configured printers
are listed as available until a job discovers a connection error.

## Reproducible checks

From repository root (use the SDK's CMake if not on PATH):

```sh
make build/rastertodeli build/raw_raster
cmake -S android/app/src/main/cpp -B build/android-native -DCMAKE_BUILD_TYPE=Release
cmake --build build/android-native --target encoder_host -j4
python3 android/tests/compare_encoder.py build/android-native/encoder_host
make test
```

The host target uses the same embedded encoder and pinned JPEG build as JNI.
All 16 golden source-input jobs must match Linux payloads byte-for-byte, including
mono calibration; this does not assert that Android PDF rasterization matches GDI.

Emulator (API 35 x86_64, host loopback only):

```sh
sdkmanager 'emulator' 'system-images;android-35;google_apis;x86_64'
avdmanager create avd -n deli35 -k 'system-images;android-35;google_apis;x86_64' --device pixel_2
emulator -avd deli35 -no-snapshot
cd android
./gradlew assembleDebug assembleDebugAndroidTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell settings put secure enabled_print_services com.deli.print/.DeliPrintService
cd ..
python3 android/tests/fake_printer.py build/android-e2e/capture.prn
# Separate terminal; keep emulator UI in English for selector text:
adb shell am instrument -w com.deli.print.test/androidx.test.runner.AndroidJUnitRunner
python3 tools/parse_deli.py build/android-e2e/capture.prn --output build/android-e2e/page
```

Instrumentation tests JNI planner 1–7 pages/all passes/orders, empty/error cases,
printer persistence and invalid addresses/fds/bands, and PrintManager → system
print dialog → discovered 10.0.2.2 printer → native encoding → TCP capture.
The PDF test activity is debug-only, not shipped in release APKs.
