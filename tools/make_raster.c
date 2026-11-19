#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc!=5 && argc!=6) { fprintf(stderr,"usage: make_raster rgb|gray height pages input.ppm [invalid-field]\n"); return 1; }
    unsigned int w=384, h=(unsigned int)strtoul(argv[2],NULL,10);
    int gray=!strcmp(argv[1],"gray"), pages=atoi(argv[3]);
    if ((!gray && strcmp(argv[1],"rgb")) || !h || h>1000 || pages<1 || pages>7) return 1;
    unsigned int channels=gray ? 1 : 3;
    FILE *image=fopen(argv[4],"wb"); if (!image) return 1;
    fprintf(image,"P%d\n%u %u\n255\n",gray ? 5 : 6,w,h);
    cups_raster_t *r=cupsRasterOpen(STDOUT_FILENO,CUPS_RASTER_WRITE);
    if (!r) return 1;
    unsigned char row[384*6+6];
    for (int page=0;page<pages;page++) {
        cups_page_header2_t hdr; memset(&hdr,0,sizeof(hdr));
        hdr.HWResolution[0]=hdr.HWResolution[1]=600;
        hdr.PageSize[0]=595; hdr.PageSize[1]=842;
        hdr.cupsWidth=w; hdr.cupsHeight=h; hdr.cupsBitsPerColor=8;
        hdr.cupsBitsPerPixel=channels*8; hdr.cupsNumColors=channels;
        hdr.cupsBytesPerLine=w*channels; hdr.cupsColorOrder=CUPS_ORDER_CHUNKED;
        hdr.cupsColorSpace=gray ? CUPS_CSPACE_W : CUPS_CSPACE_RGB;
        hdr.NumCopies=1;
        if (argc==6) {
            if (!strcmp(argv[5],"resolution")) hdr.HWResolution[0]=300;
            else if (!strcmp(argv[5],"depth")) {
                hdr.cupsBitsPerColor=16; hdr.cupsBitsPerPixel=48;
                hdr.cupsBytesPerLine=w*6;
            }
            else if (!strcmp(argv[5],"duplex")) hdr.Duplex=1;
            else if (!strcmp(argv[5],"colorspace")) {
                hdr.cupsColorSpace=CUPS_CSPACE_CMYK; hdr.cupsNumColors=4;
                hdr.cupsBitsPerPixel=32; hdr.cupsBytesPerLine=w*4;
            }
            else if (!strcmp(argv[5],"mixed")) {
                if (page) {
                    hdr.cupsColorSpace=CUPS_CSPACE_W; hdr.cupsNumColors=1;
                    hdr.cupsBitsPerPixel=8; hdr.cupsBytesPerLine=w;
                }
            } else if (strcmp(argv[5],"pagecode")) return 1;
        }
        if (!cupsRasterWriteHeader2(r,&hdr)) {
            fprintf(stderr,"raster header: %s\n",cupsRasterErrorString()); return 1;
        }
        for (unsigned int y=0;y<h;y++) {
            memset(row,0x5a,sizeof(row));
            for (unsigned int x=0;x<w;x++) {
                if (gray) row[x]=(unsigned char)((x*255)/(w-1));
                else {
                    static const unsigned char colors[][3]={{255,255,255},{255,0,0},{0,255,0},
                        {0,0,255},{0,255,255},{255,0,255},{255,255,0},{0,0,0}};
                    unsigned int patch=x/(w/8);
                    for (unsigned int c=0;c<3;c++) row[x*3+c]=y<h/2 ? colors[patch][c] :
                        (unsigned char)((x*255/(w-1)+y+c*53)%256);
                }
                if (y%64<2 || x%96<2) for (unsigned int c=0;c<channels;c++) row[x*channels+c]=0;
                if (argc==6 && !strcmp(argv[5],"pagecode"))
                    for (unsigned int c=0;c<channels;c++) row[x*channels+c]=(unsigned char)((page+1)*25);
            }
            if (!page && fwrite(row,1,w*channels,image)!=w*channels) return 1;
            if (cupsRasterWritePixels(r,row,hdr.cupsBytesPerLine)!=hdr.cupsBytesPerLine) {
                fprintf(stderr,"raster pixels: %s\n",cupsRasterErrorString()); return 1;
            }
        }
    }
    cupsRasterClose(r); return fclose(image) ? 1 : 0;
}
