#include <cups/cups.h>
#include <cups/raster.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <setjmp.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <jpeglib.h>

typedef struct { unsigned char data[1024]; size_t n; } Record;
typedef struct { const char *option, *wire; unsigned char border, media; } Paper;
static const Paper papers[] = {
    {"A4", "A4", 0, 0xff}, {"Letter", "LETTER", 0, 0xff},
    {"A5", "A5", 0, 0xff}, {"Photo4x6", "R4", 1, 0xdd}
};
static volatile sig_atomic_t cancelled;
static void cancel_job(int sig) { (void)sig; cancelled = 1; }
static void fail(const char *s) { fprintf(stderr, "ERROR: %s\n", s); exit(1); }
static void put(Record *r, unsigned int x) {
    if (r->n == sizeof(r->data)) fail("Record overflow");
    r->data[r->n++] = (unsigned char)x;
}
static void u16(Record *r, unsigned int x) { put(r,x); put(r,x>>8); }
static void u32(Record *r, uint32_t x) { u16(r,x); u16(r,x>>16); }
static void bytes(Record *r, const void *s, size_t n) {
    const unsigned char *p = s;
    while (n--) put(r,*p++);
}
static void hex(Record *r, const char *s) {
    unsigned int x; int used;
    while (*s) {
        if (sscanf(s,"%2x%n",&x,&used) != 1) fail("Invalid internal record");
        put(r,x); s += used; while (*s == ' ') s++;
    }
}
static void out(const void *p, size_t n) {
    if (cancelled) fail("Job cancelled");
    if (fwrite(p,1,n,stdout) != n) fail("Cannot write print stream");
}
static void emit(Record *r) { out(r->data,r->n); }
static void text(const char *s) { out(s,strlen(s)); }
static void typed8(Record *r, unsigned int value, unsigned int attr) {
    put(r,0xc0); put(r,value); put(r,0xf8); put(r,attr);
}
static void typed16(Record *r, unsigned int value, unsigned int attr) {
    put(r,0xc1); u16(r,value); put(r,0xf8); put(r,attr);
}
static void quoted(const char *prefix, const char *s) {
    text(prefix);
    /* User-controlled PJL fields must never be able to inject commands. */
    for (size_t i=0; s[i] && i<255; i++) {
        unsigned char c=(unsigned char)s[i];
        if (c < 32 || c == 127 || c == '"' || c == '\\') c='_';
        out(&c,1);
    }
    text("\"\n");
}
static void job_start(const char *user, const char *title, const char *quality, int gray) {
    char id[80], date[80]; time_t now=time(NULL);
    /* TODO(golden): Windows uses FILETIME and host identity; these are portable equivalents. */
    snprintf(id,sizeof(id),"DELIPRINT_%016llx",(unsigned long long)now);
    snprintf(date,sizeof(date),"@PJL SET FDATETIME=%llu.%llu\n",
             (unsigned long long)(now/86400),(unsigned long long)(now%86400));
    text("\033%-12345X@PJL JOB\n@PJL SET STRINGCODESET=UTF8\n");
    quoted("@PJL SET USERNAME=\"",user);
    text("@PJL SET LMULTIPAGEPRINT=OFF\n@PJL COMMENT Deli CUPS experimental\n");
    /* TODO(golden): host metadata is not yet compared with a Windows spool. */
    text("@PJL LJOBINFO USERID=\"");
    for (size_t i=0; user[i] && i<255; i++) {
        unsigned char c=(unsigned char)user[i];
        if (c<32 || c==127 || c=='"' || c=='\\') c='_';
        out(&c,1);
    }
    text("\" HOSTID=\"CUPS\"\n");
    quoted("@PJL SET JOBNAME=\"",title);
    /* TODO(golden): conservative defaults for OEM private DEVMODE controls. */
    text("@PJL SET ECONOMODE=OFF\n@PJL SET FIMPROVE=OFF\n"
         "@PJL SET FGHOST=OFF\n@PJL SET FDENSITY=OFF\n@PJL SET PNPQIMPROVE=OFF\n");
    quoted("@PJL SET FPRINTFILEID=\"",id); text(date);
    text("@PJL SET LPARM:PCL LFONTPRIORITY=NORESOLUTION\n@PJL SET TIMEOUT=0\n");
    text(gray ? "@PJL SET LCOLORMODEL=BLACK\n@PJL SET LINKSET=BLACKONLY\n" :
                "@PJL SET LCOLORMODEL=CMYK\n@PJL SET LINKSET=AUTOMATIC\n");
    text("@PJL SET LSHARPEN=OFF\n@PJL SET LCTPREFERENCE=IMAGE\n@PJL SET PRINTQUALITY=");
    text(quality); text("\n@PJL SET LPAGEMODE=NORMAL\n@PJL SET LCOLLATION=OFF\n"
                       "@PJL SET PAGEPROTECT=OFF\n@PJL SET RESOLUTION=600\n"
                       "@PJL ENTER LANGUAGE=PCLXL\n"
                       ") HP-PCL XL;2;1;Comment Copyright(c) 1999 Deli Group\n");
    Record r={.n=0}; put(&r,0xd1); u16(&r,600); u16(&r,600);
    hex(&r,"f8 89 c0 00 f8 86 c0 06 f8 8f 41 c0 00 f8 88 c0 01 f8 82 48 c8 c0 14");
    bytes(&r,"Deli Enhanced XL=1.2",20); hex(&r,"f8 81 47"); emit(&r);
}
static void page_start(const Paper *p, unsigned int media, unsigned int quality, int gray, unsigned int copies) {
    Record r={.n=0};
    /* 1800147c0, simplex path. */
    hex(&r,"c0 01 f8 26 c0 00 f8 28");
    typed8(&r,media,0x27); typed16(&r,copies,0x31);
    hex(&r,"c8 c0"); put(&r,(unsigned int)strlen(p->wire));
    bytes(&r,p->wire,strlen(p->wire)); hex(&r,"f8 25");
    /* TODO(golden): select OEM borderless R4 entry; runtime L511W model mask not captured. */
    typed8(&r,p->border ? 1 : 2,0xed); put(&r,0x43);
    hex(&r,"d5 00 00 80 3f 00 00 80 3f f8 2b 77 c0 01 f8 47 71 c0 01 f8 48 72");
    /* TODO(golden): private DEVMODE color selector: 0 appears RGB, nonzero gray. */
    typed8(&r,gray ? 1 : 2,3); put(&r,0x6a);
    put(&r,0xd3); u16(&r,p->border ? 0 : 96); u16(&r,p->border ? 0 : 96);
    hex(&r,"f8 2a 75"); typed8(&r,quality,0xef); typed8(&r,1,0xee); put(&r,0x40);
    emit(&r);
}
struct JpegError { struct jpeg_error_mgr base; jmp_buf jump; };
static void jpeg_error(j_common_ptr c) {
    struct JpegError *e=(struct JpegError *)c->err;
    (*c->err->output_message)(c); longjmp(e->jump,1);
}
static unsigned char *encode(unsigned char *pixels, unsigned int w, unsigned int h,
                             int gray, int quality, unsigned long *size) {
    struct jpeg_compress_struct c; struct JpegError e;
    unsigned char *mem=NULL;
    memset(&c,0,sizeof(c)); c.err=jpeg_std_error(&e.base); e.base.error_exit=jpeg_error;
    if (setjmp(e.jump)) { jpeg_destroy_compress(&c); fail("JPEG encoding failed"); }
    jpeg_create_compress(&c); jpeg_mem_dest(&c,&mem,size);
    c.image_width=w; c.image_height=h; c.input_components=gray ? 1 : 3;
    /* TODO(golden): Windows passes EXT_BGR after its buffer handling; CUPS input is RGB.
       Verify channel ordering at that callback boundary against the golden color bars. */
    c.in_color_space=gray ? JCS_GRAYSCALE : JCS_RGB;
    jpeg_set_defaults(&c); jpeg_set_quality(&c,quality,TRUE);
    /* 18000c100: option 3 sets 2x1 luma and 1x1 chroma (4:2:2). */
    if (!gray) { c.comp_info[0].h_samp_factor=2; c.comp_info[0].v_samp_factor=1; }
    c.optimize_coding=FALSE; c.dct_method=JDCT_ISLOW;
    /* TODO(golden): standard IJG tables/default integer DCT inferred from linked libjpeg-turbo.
       No Windows spool yet proves table bytes or optional pre-JPEG enhancement equivalence. */
    jpeg_start_compress(&c,TRUE);
    while (c.next_scanline<c.image_height) {
        JSAMPROW row=pixels+(size_t)c.next_scanline*w*(gray ? 1u : 3u);
        jpeg_write_scanlines(&c,&row,1);
    }
    jpeg_finish_compress(&c); jpeg_destroy_compress(&c); return mem;
}
static unsigned char *jpeg_payload(unsigned char *jpeg, unsigned long *n, unsigned int h) {
    size_t pos=2;
    if (*n<4 || jpeg[0]!=0xff || jpeg[1]!=0xd8) fail("Invalid encoder JPEG");
    while (pos+4<*n) {
        if (jpeg[pos]!=0xff) fail("Invalid JPEG segment");
        unsigned int marker=jpeg[pos+1], len=(jpeg[pos+2]<<8)|jpeg[pos+3];
        if (len<2 || len>*n-pos-2) fail("Invalid JPEG segment length");
        if (marker==0xda) {
            /* Windows starts two bytes BEFORE entropy data, then writes ff 2c. */
            pos+=len; *n-=(unsigned long)pos;
            jpeg+=pos; jpeg[0]=0xff; jpeg[1]=0x2c;
            if (*n<4 || jpeg[*n-2]!=0xff || jpeg[*n-1]!=0xd9) fail("Invalid JPEG tail");
            static const unsigned char tokens[]={0xd7,0xd0,0xd1,0xd2,0xd3,0xd4,0xd5,0xd6};
            jpeg[*n-1]=tokens[((h+7)/8)%8]; return jpeg;
        }
        pos+=len+2;
    }
    fail("Missing JPEG scan"); return NULL;
}
static void band(unsigned char *pixels, unsigned int w, unsigned int h, unsigned int y,
                 int gray, int quality) {
    unsigned long n=0; unsigned char *jpeg=encode(pixels,w,h,gray,quality,&n);
    unsigned char *payload=jpeg_payload(jpeg,&n,h);
    if (n>UINT32_MAX) fail("JPEG band too large");
    uint32_t sum=0xfa, len=(uint32_t)n;
    for (unsigned int i=0;i<4;i++) sum+=(len>>(8*i))&255;
    for (unsigned long i=0;i<n;i++) sum+=payload[i];
    Record r={.n=0};
    hex(&r,"c0 cc f8 2c 7b d3 00 00"); u16(&r,y);
    hex(&r,"f8 4c 6b c0 00 f8 64 c0 02 f8 62");
    typed16(&r,w,0x6c); typed16(&r,h,0x6b); put(&r,0xd1); u16(&r,w); u16(&r,h);
    hex(&r,"f8 67 c0 08 f8 fa c0 02 f8 f9 c1 00 00 f8 f8");
    typed16(&r,600,0xf7); hex(&r,"c1 06 00 f8 f6 b0");
    typed16(&r,0,0x6d); typed16(&r,h,0x63); typed8(&r,0xf6,0x65);
    put(&r,0xc2); u32(&r,sum); hex(&r,"f8 f5 b1 fa"); u32(&r,len);
    if (r.n!=89) fail("Invalid BeginImage size");
    emit(&r); out(payload,n);
    r.n=0; typed16(&r,0,0x6d); typed16(&r,h,0x63); typed8(&r,0xf7,0x65);
    hex(&r,"c2 aa 00 00 00 f8 f5 b1 fa 01 00 00 00 aa b2");
    if (r.n!=29) fail("Invalid EndImage size");
    emit(&r); free(jpeg);
}
static const Paper *paper_for(const char *name, const cups_page_header2_t *h) {
    if (name) {
        for (size_t i=0;i<sizeof(papers)/sizeof(*papers);i++)
            if (!strcmp(name,papers[i].option)) return &papers[i];
        fail("Unsupported PageSize (A4, Letter, A5, Photo4x6 only)");
    }
    unsigned int w=h->PageSize[0], ht=h->PageSize[1];
    if (w>=593 && w<=597 && ht>=840 && ht<=844) return &papers[0];
    if (w==612 && ht==792) return &papers[1];
    if (w>=418 && w<=422 && ht>=593 && ht<=597) return &papers[2];
    if (w>=287 && w<=291 && ht>=430 && ht<=433) return &papers[3];
    fail("Unrecognized raster page size"); return NULL;
}
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
int main(int argc, char **argv) {
    if (argc!=6 && argc!=7) fail("Usage: rastertodeli job-id user title copies options [raster-file]");
    signal(SIGTERM,cancel_job); signal(SIGINT,cancel_job); signal(SIGPIPE,SIG_IGN);
    char *end; long copies=strtol(argv[4],&end,10);
    if (*end || copies<1 || copies>65535) fail("Invalid copy count");
    cups_option_t *opts=NULL; int count=cupsParseOptions(argv[5],0,&opts);
    const char *quality=cupsGetOption("DeliQuality",count,opts);
    const char *q="NORMAL";
    if (quality) {
        if (!strcmp(quality,"High")) q="HIGH";
        else if (!strcmp(quality,"Draft")) q="DRAFT";
        else if (strcmp(quality,"Normal")) fail("Unsupported DeliQuality");
    }
    const char *media=cupsGetOption("MediaType",count,opts);
    unsigned int override=0;
    if (media) {
        if (!strcmp(media,"Auto")) override=0;
        else if (!strcmp(media,"Plain")) override=0xff;
        else if (!strcmp(media,"Photo")) override=0xdd;
        else if (!strcmp(media,"Matte")) override=0xdc;
        else if (!strcmp(media,"Envelope")) override=0xf7;
        else if (!strcmp(media,"Postcard")) override=0xf6;
        else fail("Unsupported MediaType");
    }
    if (override==0xdd && !strcmp(q,"DRAFT")) q="NORMAL";
    int fd=argc==7 ? open(argv[6],O_RDONLY) : STDIN_FILENO;
    if (fd<0) fail("Cannot open raster input");
    cups_raster_t *ras=cupsRasterOpen(fd,CUPS_RASTER_READ);
    if (!ras) fail("Cannot open CUPS raster");
    cups_page_header2_t h; unsigned int pages=0; int jobgray=-1;
    while (cupsRasterReadHeader2(ras,&h)) {
        int gray=validate(&h);
        if (jobgray!=-1 && gray!=jobgray) fail("Mixed RGB/gray jobs are not supported");
        const Paper *p=paper_for(cupsGetOption("PageSize",count,opts),&h);
        unsigned int m=override ? override : p->media;
        unsigned int jq=90;
        /* TODO(golden): omit Windows model-specific sharpening/gamma/line enhancement.
           Raw socket jobs use JPEG quality 90; High/Draft change PJL, not JPEG tables. */
        if (!pages) {
            if (m==0xdd && !strcmp(q,"DRAFT")) q="NORMAL";
            job_start(argv[2],argv[3],q,gray); jobgray=gray;
        }
        page_start(p,m,jq,gray,(unsigned int)copies);
        unsigned int stride=h.cupsWidth*(gray ? 1u : 3u);
        unsigned char *row=malloc(h.cupsBytesPerLine), *pixels=malloc((size_t)stride*256);
        if (!row || !pixels) fail("Out of memory");
        for (unsigned int y=0;y<h.cupsHeight;) {
            unsigned int rows=h.cupsHeight-y; if (rows>256) rows=256;
            for (unsigned int j=0;j<rows;j++) {
                if (cancelled) fail("Job cancelled");
                if (cupsRasterReadPixels(ras,row,h.cupsBytesPerLine)!=h.cupsBytesPerLine)
                    fail("Truncated raster pixels");
                memcpy(pixels+(size_t)j*stride,row,stride);
            }
            band(pixels,h.cupsWidth,rows,y,gray,(int)jq); y+=rows;
        }
        free(row); free(pixels);
        Record r={.n=0}; typed16(&r,(unsigned int)copies,0x31); put(&r,0x44); emit(&r);
        pages++; fprintf(stderr,"PAGE: %u %ld\n",pages,copies);
    }
    const char *error=cupsRasterErrorString();
    if (error && *error) fail(error);
    if (!pages) fail("No raster pages");
    text("\x49\x42\033%-12345X@PJL EOJ\n@PJL LPORTROTATE\n\033%-12345X");
    cupsRasterClose(ras); if (argc==7) close(fd); cupsFreeOptions(count,opts);
    if (fflush(stdout) || ferror(stdout)) fail("Output write failed");
    return 0;
}
