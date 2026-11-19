#include "resample.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    const unsigned int w=19,h=73;
    for (unsigned int scale=2;scale<=4;scale+=2) {
        unsigned char *src=malloc((size_t)w*h*scale*scale*4);
        unsigned char full[19*73*4], tiles[19*73*4];
        assert(src);
        for (size_t i=0;i<(size_t)w*h*scale*scale*4;i++) src[i]=(unsigned char)(i*19+i/13);
        for (unsigned int kernel=DELI_BOX;kernel<=DELI_MITCHELL;kernel++) {
            assert(deli_downsample(src,w,h*scale,scale,0,h,kernel,full));
            for (unsigned int y=0;y<h;) {
                unsigned int rows=h-y>17 ? 17 : h-y;
                unsigned int first=y>3 ? y-3 : 0, last=y+rows+3<h ? y+rows+3 : h;
                assert(deli_downsample(src+(size_t)first*scale*w*scale*4,w,(last-first)*scale,
                    scale,y-first,rows,kernel,tiles+(size_t)y*w*4));
                y+=rows;
            }
            assert(!memcmp(full,tiles,sizeof(full)));
            memset(src,255,(size_t)w*h*scale*scale*4);
            assert(deli_downsample(src,w,h*scale,scale,0,h,kernel,tiles));
            for (size_t i=0;i<sizeof(tiles);i++) assert(tiles[i]==255);
            for (size_t i=0;i<(size_t)w*h*scale*scale*4;i++) src[i]=(unsigned char)(i*19+i/13);
        }
        assert(deli_downsample(src,w,h*scale,scale,0,h,DELI_BOX,full));
        for (unsigned int y=0;y<h;y++) for (unsigned int x=0;x<w;x++) for (unsigned int c=0;c<3;c++) {
            unsigned int sum=0;
            for (unsigned int j=0;j<scale;j++) for (unsigned int i=0;i<scale;i++)
                sum+=src[(((size_t)y*scale+j)*w*scale+x*scale+i)*4+c];
            assert(full[((size_t)y*w+x)*4+c]==(sum+scale*scale/2)/(scale*scale));
        }
        free(src);
    }
    unsigned char pixel[16]={0},out[4];
    assert(!deli_downsample(NULL,1,2,2,0,1,DELI_BOX,out));
    assert(!deli_downsample(pixel,1,2,2,0,0,DELI_BOX,out));
    assert(!deli_downsample(pixel,1,2,3,0,1,DELI_BOX,out));
    assert(!deli_downsample(pixel,1,2,2,1,1,DELI_BOX,out));
    assert(!deli_downsample(pixel,1,2,2,0,1,99,out));
    puts("PASS: 2x/4x box/Lanczos3/Mitchell: tiled == full (kernel halos), constant/edge pixels, exact box averages; empty/invalid rejected");
    return 0;
}
