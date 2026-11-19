#include "deli.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int validate(const cups_page_header2_t *h) {
    int gray=h->cupsColorSpace==CUPS_CSPACE_W;
    unsigned int components=gray ? 1 : 3;
    if ((!gray && h->cupsColorSpace!=CUPS_CSPACE_RGB) || h->cupsBitsPerColor!=8 ||
        h->cupsBitsPerPixel!=8*components || h->cupsNumColors!=components ||
        h->cupsColorOrder!=CUPS_ORDER_CHUNKED || h->HWResolution[0]!=600 ||
        h->HWResolution[1]!=600 || h->Duplex ||
        !h->cupsWidth || !h->cupsHeight || h->cupsWidth>65535 || h->cupsHeight>65535 ||
        h->cupsBytesPerLine<h->cupsWidth*components || h->cupsBytesPerLine>1024*1024)
        fail("Require 600dpi chunky RGB24 or W8, simplex, dimensions 1..65535");
    return gray;
}

typedef struct { cups_page_header2_t header; off_t offset; } CachedPage;
int main(int argc, char **argv) {
    DeliOptions o=deli_options(argc,argv);
    int fd=argc==7 ? open(argv[6],O_RDONLY) : STDIN_FILENO;
    if (fd<0) fail("Cannot open raster input");
    cups_raster_t *ras=cupsRasterOpen(fd,CUPS_RASTER_READ);
    FILE *cache=tmpfile();
    if (!ras || !cache) fail("Cannot open raster cache");
    cups_page_header2_t h; CachedPage *pages=NULL; unsigned int count=0;
    int jobgray=-1;
    while (cupsRasterReadHeader2(ras,&h)) {
        int gray=validate(&h) || o.forcegray;
        if (jobgray!=-1 && gray!=jobgray) fail("Mixed RGB/gray jobs are not supported");
        jobgray=gray;
        if (count==1000000) fail("Too many pages");
        CachedPage *next=realloc(pages,((size_t)count+1)*sizeof(*pages));
        if (!next) fail("Out of memory");
        pages=next; pages[count].header=h; pages[count].offset=ftello(cache);
        if (pages[count].offset<0) fail("Cannot seek raster cache");
        unsigned char *row=malloc(h.cupsBytesPerLine);
        if (!row) fail("Out of memory");
        for (unsigned int y=0;y<h.cupsHeight;y++) {
            deli_check_cancel();
            if (cupsRasterReadPixels(ras,row,h.cupsBytesPerLine)!=h.cupsBytesPerLine)
                fail("Truncated raster pixels");
            if (fwrite(row,1,h.cupsBytesPerLine,cache)!=h.cupsBytesPerLine)
                fail("Cannot write raster cache");
        }
        free(row); count++;
    }
    const char *error=cupsRasterErrorString();
    if (error && *error) fail(error);
    if (!count) fail("No raster pages");
    cupsRasterClose(ras); if (argc==7) close(fd);
    const char *manual=cupsGetOption("DeliDuplex",o.count,o.opts);
    DeliPlan plan=deli_plan(count,&o,manual && strcmp(manual,"Off"));
    for (size_t i=0;i<plan.count;i++) {
        unsigned int number=plan.pages[i];
        CachedPage *page=&pages[number ? number-1 : 0]; h=page->header;
        const Paper *p=o.paper ? o.paper : paper_for(NULL,&h);
        unsigned int media=o.media ? o.media : p->media;
        if (!i) job_start(argv[2],argv[3],media==0xdd && !strcmp(o.quality,"DRAFT") ?
                         "NORMAL" : o.quality,jobgray);
        page_start(p,media,90,jobgray,o.copies);
        if (fseeko(cache,page->offset,SEEK_SET)) fail("Cannot seek raster cache");
        unsigned int stride=h.cupsWidth*(jobgray ? 1u : 3u);
        unsigned char *row=malloc(h.cupsBytesPerLine), *pixels=malloc((size_t)stride*256);
        if (!row || !pixels) fail("Out of memory");
        for (unsigned int y=0;y<h.cupsHeight;) {
            unsigned int rows=h.cupsHeight-y; if (rows>256) rows=256;
            for (unsigned int j=0;j<rows;j++) {
                unsigned char *dest=pixels+(size_t)j*stride;
                if (!number) memset(dest,255,stride);
                else {
                    if (fread(row,1,h.cupsBytesPerLine,cache)!=h.cupsBytesPerLine)
                        fail("Cannot read raster cache");
                    if (!jobgray) memcpy(dest,row,stride);
                    else deli_mono(dest,row,h.cupsWidth,h.cupsColorSpace==CUPS_CSPACE_W);
                }
            }
            band(pixels,h.cupsWidth,rows,y,jobgray,90); y+=rows;
        }
        free(row); free(pixels); deli_page_end(o.copies);
        fprintf(stderr,"PAGE: %zu %u\n",i+1,o.copies);
    }
    if (plan.count) deli_job_end();
    free(plan.pages); free(pages); fclose(cache); cupsFreeOptions(o.count,o.opts);
    return 0;
}
