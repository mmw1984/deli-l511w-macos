#include "deli.h"
#include <ApplicationServices/ApplicationServices.h>
#include <limits.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static char temporary[PATH_MAX];
static void cleanup(void) { if (*temporary) unlink(temporary); }

static CGPDFDocumentRef open_pdf(int argc, char **argv) {
    const char *path=argc==7 ? argv[6] : temporary;
    if (argc!=7) {
        const char *dir=getenv("TMPDIR"); if (!dir) dir="/tmp";
        if (snprintf(temporary,sizeof(temporary),"%s/deli-pdf-XXXXXX",dir)>=(int)sizeof(temporary))
            fail("Temporary path too long");
        int fd=mkstemp(temporary);
        if (fd<0) fail("Cannot create PDF temporary file");
        atexit(cleanup);
        FILE *file=fdopen(fd,"wb"); if (!file) { close(fd); fail("Cannot open PDF temporary file"); }
        unsigned char data[65536]; size_t n;
        while ((n=fread(data,1,sizeof(data),stdin))!=0) {
            deli_check_cancel();
            if (fwrite(data,1,n,file)!=n) fail("Cannot cache PDF input");
        }
        if (ferror(stdin) || fclose(file)) fail("Cannot read PDF input");
    }
    CFURLRef url=CFURLCreateFromFileSystemRepresentation(kCFAllocatorDefault,
        (const UInt8 *)path,(CFIndex)strlen(path),false);
    if (!url) fail("Cannot create PDF URL");
    CGPDFDocumentRef pdf=CGPDFDocumentCreateWithURL(url); CFRelease(url);
    if (!pdf || !CGPDFDocumentIsUnlocked(pdf)) fail("Invalid or locked PDF");
    return pdf;
}

static void render(CGPDFPageRef page, unsigned char *bitmap, unsigned int w,
                   unsigned int h, unsigned int pw, unsigned int ph, int smooth,
                   unsigned int offset) {
    CGColorSpaceRef space=CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
    if (!space) fail("Cannot create RGB color space");
    CGContextRef ctx=CGBitmapContextCreate(bitmap,w,h,8,(size_t)w*4,space,
        kCGBitmapByteOrder32Big | kCGImageAlphaNoneSkipLast);
    CGColorSpaceRelease(space);
    if (!ctx) fail("Cannot create PDF bitmap context");
    CGContextSetRGBFillColor(ctx,1,1,1,1);
    CGContextFillRect(ctx,CGRectMake(0,0,w,h));
    CGContextSetShouldAntialias(ctx,smooth);
    CGContextSetAllowsAntialiasing(ctx,smooth);
    CGContextSetAllowsFontSmoothing(ctx,false);
    CGContextSetShouldSmoothFonts(ctx,false);
    CGContextSetInterpolationQuality(ctx,kCGInterpolationHigh);
    if (page) {
        CGRect box=CGRectIntersection(CGPDFPageGetBoxRect(page,kCGPDFCropBox),
                                     CGPDFPageGetBoxRect(page,kCGPDFMediaBox));
        int angle=CGPDFPageGetRotationAngle(page)%180;
        double bw=angle ? box.size.height : box.size.width;
        double bh=angle ? box.size.width : box.size.height;
        if (!isfinite(bw) || !isfinite(bh) || bw<=0 || bh<=0) fail("Invalid PDF page size");
        int rotate=(bw>bh)!=(pw>ph) ? 90 : 0;
        double target_w=(double)pw*72/600, target_h=(double)ph*72/600;
        double rw=rotate ? bh : bw, rh=rotate ? bw : bh;
        CGRect target=CGRectMake(0,0,w,h);
        if (fabs(rw-target_w)<1 && fabs(rh-target_h)<1)
            target=CGRectMake(-(double)offset,-((double)ph-offset-h),pw,ph);
        double scale=fmin(target.size.width/rw,target.size.height/rh);
        CGContextTranslateCTM(ctx,target.origin.x+(target.size.width-rw*scale)/2,
                              target.origin.y+(target.size.height-rh*scale)/2);
        CGContextScaleCTM(ctx,scale,scale);
        CGAffineTransform transform=CGPDFPageGetDrawingTransform(page,kCGPDFCropBox,
            CGRectMake(0,0,rw,rh),rotate,true);
        CGContextConcatCTM(ctx,transform);
        CGContextDrawPDFPage(ctx,page);
    }
    CGContextRelease(ctx);
}

int main(int argc, char **argv) {
    DeliOptions o=deli_options(argc,argv);
    const char *rendering=cupsGetOption("DeliRendering",o.count,o.opts);
    if (rendering && strcmp(rendering,"Crisp") && strcmp(rendering,"Smooth"))
        fail("Unsupported DeliRendering");
    int smooth=rendering && !strcmp(rendering,"Smooth");
    const char *resolution=cupsGetOption("Resolution",o.count,o.opts);
    if (resolution && strcmp(resolution,"600dpi")) fail("Require 600dpi");
    const char *sides=cupsGetOption("sides",o.count,o.opts);
    if (sides && strcmp(sides,"one-sided")) fail("Use DeliDuplex for manual duplex");
    cups_page_header2_t header={0};
    const Paper *paper=o.paper ? o.paper : paper_for("A4",&header);
    unsigned int w,h,pw,ph; deli_geometry(paper,&w,&h,&pw,&ph);
    CGPDFDocumentRef pdf=open_pdf(argc,argv);
    size_t total=CGPDFDocumentGetNumberOfPages(pdf);
    if (!total || total>1000000) fail("PDF has no pages or too many pages");
    DeliPlan plan=deli_plan((unsigned int)total,&o,1);
    if (!plan.count) {
        free(plan.pages); CGPDFDocumentRelease(pdf); cupsFreeOptions(o.count,o.opts);
        return 0;
    }
    unsigned char *bitmap=malloc((size_t)w*h*4), *rgb=malloc((size_t)w*3);
    unsigned char *pixels=malloc((size_t)w*256*(o.forcegray ? 1u : 3u));
    if (!bitmap || !pixels || !rgb) fail("Out of memory");
    unsigned int media=o.media ? o.media : paper->media;
    if (plan.count) job_start(argv[2],argv[3],media==0xdd && !strcmp(o.quality,"DRAFT") ?
                             "NORMAL" : o.quality,o.forcegray);
    for (size_t i=0;i<plan.count;i++) {
        deli_check_cancel();
        CGPDFPageRef page=plan.pages[i] ? CGPDFDocumentGetPage(pdf,plan.pages[i]) : NULL;
        if (plan.pages[i] && !page) fail("Cannot load PDF page");
        render(page,bitmap,w,h,pw,ph,smooth,paper->border ? 0 : 96);
        page_start(paper,media,90,o.forcegray,o.copies);
        size_t stride=(size_t)w*(o.forcegray ? 1u : 3u);
        for (unsigned int y=0;y<h;) {
            unsigned int rows=h-y; if (rows>256) rows=256;
            for (unsigned int j=0;j<rows;j++) {
                const unsigned char *src=bitmap+(size_t)(y+j)*w*4;
                for (unsigned int x=0;x<w;x++) memcpy(rgb+x*3,src+x*4,3);
                unsigned char *dest=pixels+j*stride;
                if (o.forcegray) deli_mono(dest,rgb,w,0);
                else memcpy(dest,rgb,stride);
            }
            band(pixels,w,rows,y,o.forcegray,90); y+=rows;
        }
        deli_page_end(o.copies); fprintf(stderr,"PAGE: %zu %u\n",i+1,o.copies);
    }
    if (plan.count) deli_job_end();
    free(bitmap); free(rgb); free(pixels); free(plan.pages);
    CGPDFDocumentRelease(pdf); cupsFreeOptions(o.count,o.opts);
    return 0;
}
