#ifndef DELI_RESAMPLE_H
#define DELI_RESAMPLE_H

enum { DELI_BOX, DELI_LANCZOS3, DELI_MITCHELL };
/* Opaque 4-byte pixels; source is width*scale by height, top/rows are output rows. */
int deli_downsample(const unsigned char *src, unsigned int width, unsigned int height,
                    unsigned int scale, unsigned int top, unsigned int rows,
                    unsigned int kernel, unsigned char *dst);

#endif
