CC ?= cc
CPPFLAGS += -D_POSIX_C_SOURCE=200809L
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic
JPEG_CFLAGS ?= $(shell pkg-config --cflags libjpeg)
JPEG_LIBS ?= $(shell pkg-config --libs libjpeg)
ifeq ($(shell uname -s),Darwin)
CPPFLAGS += -D_DARWIN_C_SOURCE
CUPS_LIBS ?= -lcups
else
CUPS_LIBS ?= -lcupsimage -lcups
endif

all: build/rastertodeli build/make_raster
ifeq ($(shell uname -s),Darwin)
all: build/pdftodeli
endif

ENCODER = src/deli.c src/page_plan.c
HEADERS = src/deli.h src/page_plan.h

build:
	mkdir -p $@

build/rastertodeli: src/rastertodeli.c $(ENCODER) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(JPEG_CFLAGS) $< $(ENCODER) -o $@ $(LDFLAGS) $(JPEG_LIBS) $(CUPS_LIBS)

ifeq ($(shell uname -s),Darwin)
build/pdftodeli: src/pdftodeli.c src/resample.c src/resample.h $(ENCODER) $(HEADERS) | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(JPEG_CFLAGS) $< src/resample.c $(ENCODER) -o $@ $(LDFLAGS) $(JPEG_LIBS) $(CUPS_LIBS) -framework ApplicationServices
endif

build/test_page_plan: tools/test_page_plan.c src/page_plan.c src/page_plan.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -Isrc tools/test_page_plan.c src/page_plan.c -o $@ $(LDFLAGS)

build/make_raster: tools/make_raster.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@ $(LDFLAGS) $(CUPS_LIBS)

build/test_resample: tools/test_resample.c src/resample.c src/resample.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -Isrc tools/test_resample.c src/resample.c -lm -o $@

test: all build/test_page_plan build/test_resample
	./build/test_page_plan
	./build/test_resample
	python3 tools/test_page_options.py
	python3 tools/test_pdf.py
	python3 tools/test_roundtrip.py

build/raw_raster: tools/raw_raster.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@ $(LDFLAGS) $(CUPS_LIBS)

compare-golden: all build/raw_raster
	python3 tools/compare_golden.py

.PHONY: all test compare-golden
