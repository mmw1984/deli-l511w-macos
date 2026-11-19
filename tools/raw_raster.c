#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 5) return 1;
    unsigned int w=(unsigned int)atoi(argv[1]), h=(unsigned int)atoi(argv[2]);
    unsigned int channels=atoi(argv[3]) ? 1 : 3;
    if (!w || !h || w>65535 || h>65535) return 1;
    cups_raster_t *r=cupsRasterOpen(STDOUT_FILENO,CUPS_RASTER_WRITE);
    unsigned char *row=malloc(w*channels);
    if (!r || !row) return 1;
    for (int i=4;i<argc;i++) {
        FILE *f=fopen(argv[i],"rb");
        if (!f) return 1;
        cups_page_header2_t hdr; memset(&hdr,0,sizeof(hdr));
        hdr.HWResolution[0]=hdr.HWResolution[1]=600;
        hdr.PageSize[0]=595; hdr.PageSize[1]=842;
        hdr.cupsWidth=w; hdr.cupsHeight=h; hdr.cupsBitsPerColor=8;
        hdr.cupsBitsPerPixel=channels*8; hdr.cupsNumColors=channels;
        hdr.cupsBytesPerLine=w*channels; hdr.cupsColorOrder=CUPS_ORDER_CHUNKED;
        hdr.cupsColorSpace=channels==1 ? CUPS_CSPACE_W : CUPS_CSPACE_RGB;
        if (!cupsRasterWriteHeader2(r,&hdr)) return 1;
        for (unsigned int y=0;y<h;y++)
            if (fread(row,1,w*channels,f)!=w*channels ||
                cupsRasterWritePixels(r,row,w*channels)!=w*channels) return 1;
        if (fgetc(f)!=EOF) return 1;
        fclose(f);
    }
    free(row); cupsRasterClose(r); return 0;
}
