#ifndef DELI_H
#define DELI_H
#ifndef DELI_EMBEDDED
#include <cups/cups.h>
#include <cups/raster.h>
#endif
#include "page_plan.h"
typedef struct { const char *option, *wire; unsigned char border, media; } Paper;
#ifndef DELI_EMBEDDED
typedef struct {
    cups_option_t *opts;
    int count;
    unsigned int copies;
    int forcegray;
    const char *quality;
    unsigned int media;
    const Paper *paper;
} DeliOptions;
#endif
void fail(const char *message);
void deli_check_cancel(void);
#ifndef DELI_EMBEDDED
DeliOptions deli_options(int argc, char **argv);
const Paper *paper_for(const char *name, const cups_page_header2_t *header);
#endif
void deli_geometry(const Paper *paper, unsigned int *w, unsigned int *h,
                   unsigned int *physical_w, unsigned int *physical_h);
void job_start(const char *user, const char *title, const char *quality, int gray);
void page_start(const Paper *p, unsigned int media, unsigned int quality, int gray, unsigned int copies);
void band(unsigned char *pixels, unsigned int w, unsigned int h, unsigned int y, int gray, int quality);
void deli_mono(unsigned char *dest, const unsigned char *src, unsigned int width, int inputgray);
void deli_page_end(unsigned int copies);
void deli_job_end(void);
#ifndef DELI_EMBEDDED
DeliPlan deli_plan(unsigned int total, const DeliOptions *options, int default_reverse);
#endif
#endif
