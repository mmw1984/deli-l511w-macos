CC ?= cc
CPPFLAGS += -D_POSIX_C_SOURCE=200809L
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic
JPEG_CFLAGS ?= $(shell pkg-config --cflags libjpeg)
JPEG_LIBS ?= $(shell pkg-config --libs libjpeg)
CUPS_LIBS ?= -lcupsimage -lcups

all: build/rastertodeli build/make_raster

build:
	mkdir -p $@

build/rastertodeli: src/rastertodeli.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(JPEG_CFLAGS) $< -o $@ $(LDFLAGS) $(JPEG_LIBS) $(CUPS_LIBS)

build/make_raster: tools/make_raster.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@ $(LDFLAGS) $(CUPS_LIBS)

test: all
	python3 tools/test_roundtrip.py

build/raw_raster: tools/raw_raster.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@ $(LDFLAGS) $(CUPS_LIBS)

compare-golden: all build/raw_raster
	python3 tools/compare_golden.py

.PHONY: all test compare-golden
