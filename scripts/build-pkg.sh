#!/bin/sh
set -eu

if [ "$(uname -s)" != Darwin ]; then
    echo 'build-pkg.sh requires macOS, Xcode Command Line Tools and cmake' >&2
    exit 1
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK="$ROOT/build/pkg"
DIST="$ROOT/dist"
VERSION=0.1.0
JPEG_VERSION=3.0.4
JPEG_SHA=0270f9496ad6d69e743f1e7b9e3e9398f5b4d606b6a47744df4b73df50f62e38
mkdir -p "$WORK" "$DIST"
ARCHIVE="$WORK/libjpeg-turbo-$JPEG_VERSION.tar.gz"
if [ ! -f "$ARCHIVE" ]; then
    curl --fail --location --retry 3 \
        "https://github.com/libjpeg-turbo/libjpeg-turbo/archive/refs/tags/$JPEG_VERSION.tar.gz" \
        --output "$ARCHIVE"
fi
echo "$JPEG_SHA  $ARCHIVE" | shasum -a 256 -c -
if [ ! -d "$WORK/libjpeg-turbo-$JPEG_VERSION" ]; then
    tar -xzf "$ARCHIVE" -C "$WORK"
fi
CLANG=$(xcrun --find clang)
SDK=$(xcrun --sdk macosx --show-sdk-path)
for ARCH in arm64 x86_64; do
    PREFIX="$WORK/jpeg-$ARCH"
    cmake -S "$WORK/libjpeg-turbo-$JPEG_VERSION" -B "$WORK/jpeg-build-$ARCH" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_OSX_ARCHITECTURES="$ARCH" \
        -DCMAKE_OSX_SYSROOT="$SDK" -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
        -DENABLE_SHARED=OFF -DENABLE_STATIC=ON -DWITH_TURBOJPEG=OFF \
        -DWITH_SIMD=OFF
    cmake --build "$WORK/jpeg-build-$ARCH" --config Release --parallel 3
    cmake --install "$WORK/jpeg-build-$ARCH" --config Release
    mkdir -p "$WORK/$ARCH"
    # Apple's libcups exports the raster API; no Homebrew CUPS/JPEG dylib dependency.
    "$CLANG" -std=c11 -Wall -Wextra -Wpedantic -O2 -D_POSIX_C_SOURCE=200809L -D_DARWIN_C_SOURCE \
        -arch "$ARCH" -isysroot "$SDK" -mmacosx-version-min=11.0 \
        -I"$PREFIX/include" "$ROOT/src/rastertodeli.c" "$ROOT/src/deli.c" "$ROOT/src/page_plan.c" \
        "$PREFIX/lib/libjpeg.a" -lcups -o "$WORK/$ARCH/rastertodeli"
    "$CLANG" -std=c11 -Wall -Wextra -Wpedantic -O2 -D_POSIX_C_SOURCE=200809L -D_DARWIN_C_SOURCE \
        -arch "$ARCH" -isysroot "$SDK" -mmacosx-version-min=11.0 \
        -I"$PREFIX/include" "$ROOT/src/pdftodeli.c" "$ROOT/src/deli.c" "$ROOT/src/page_plan.c" \
        "$PREFIX/lib/libjpeg.a" -lcups -framework ApplicationServices -o "$WORK/$ARCH/pdftodeli"
done
STAGE="$WORK/root"
FILTER="$STAGE/Library/Printers/Deli/filter"
PPDS="$STAGE/Library/Printers/PPDs/Contents/Resources"
mkdir -p "$FILTER" "$PPDS"
for NAME in rastertodeli pdftodeli; do
    lipo -create "$WORK/arm64/$NAME" "$WORK/x86_64/$NAME" -output "$FILTER/$NAME"
    lipo "$FILTER/$NAME" -verify_arch arm64 x86_64
    chmod 755 "$FILTER/$NAME"
    codesign --force --sign - "$FILTER/$NAME"
done
# CUPS supports an absolute filter path; avoid SIP-protected /usr/libexec/cups/filter.
sed -e 's@100 rastertodeli"@100 /Library/Printers/Deli/filter/rastertodeli"@' \
    -e 's@0 pdftodeli"@0 /Library/Printers/Deli/filter/pdftodeli"@' \
    "$ROOT/ppd/Deli-L511W.ppd" > "$PPDS/Deli-L511W.ppd"
chmod 644 "$PPDS/Deli-L511W.ppd"
install -m 644 "$WORK/libjpeg-turbo-$JPEG_VERSION/LICENSE.md" \
    "$STAGE/Library/Printers/Deli/libjpeg-turbo-LICENSE.md"
install -m 644 "$WORK/libjpeg-turbo-$JPEG_VERSION/README.ijg" \
    "$STAGE/Library/Printers/Deli/libjpeg-turbo-README.ijg"
install -m 644 "$ROOT/README.md" "$STAGE/Library/Printers/Deli/README.md"
if command -v cupstestppd >/dev/null 2>&1; then
    # Staging is user-owned; pkgbuild assigns root ownership on installation.
    test -x "$FILTER/rastertodeli"
    test -x "$FILTER/pdftodeli"
    cupstestppd -W filters -R "$STAGE" "$PPDS/Deli-L511W.ppd"
fi
otool -L "$FILTER/rastertodeli"
otool -L "$FILTER/pdftodeli"
pkgbuild --root "$STAGE" --identifier org.openprinting.experimental.deli-l511w \
    --version "$VERSION" --install-location / --ownership recommended \
    "$DIST/Deli-L511W-$VERSION-universal.pkg"
echo "Built $DIST/Deli-L511W-$VERSION-universal.pkg (unsigned installer, ad-hoc signed filter)"
