#include "resample.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>

static double weight(double x, unsigned int kernel) {
    x=fabs(x);
    if (kernel==DELI_BOX) return x<0.5 ? 1 : 0;
    if (kernel==DELI_LANCZOS3) {
        if (x<1e-12) return 1;
        if (x>=3) return 0;
        double p=3.14159265358979323846*x;
        return sin(p)*sin(p/3)/(p*p/3);
    }
    if (x<1) return (7*x*x*x-12*x*x+16.0/3)/6;
    if (x<2) return (-7.0/3*x*x*x+12*x*x-20*x+32.0/3)/6;
    return 0;
}

static unsigned int clamp(int64_t index, unsigned int limit) {
    return index<0 ? 0 : (uint64_t)index>=limit ? limit-1 : (unsigned int)index;
}

int deli_downsample(const unsigned char *src, unsigned int width, unsigned int height,
                    unsigned int scale, unsigned int top, unsigned int rows,
                    unsigned int kernel, unsigned char *dst) {
    if (!src || !dst || !width || !height || !rows || width>65535 || height>65535 ||
        (scale!=2 && scale!=4) || kernel>DELI_MITCHELL || height%scale ||
        top>height/scale || rows>height/scale-top ||
        (size_t)width>SIZE_MAX/height/scale/4 ||
        (size_t)width>SIZE_MAX/height/(3*sizeof(float))) return 0;
    if (kernel==DELI_BOX) {
        unsigned int area=scale*scale;
        for (unsigned int y=0;y<rows;y++) for (unsigned int x=0;x<width;x++) {
            unsigned int rgb[3]={0,0,0};
            for (unsigned int dy=0;dy<scale;dy++) for (unsigned int dx=0;dx<scale;dx++) {
                const unsigned char *pixel=src+(((size_t)(top+y)*scale+dy)*width*scale+x*scale+dx)*4;
                for (unsigned int c=0;c<3;c++) rgb[c]+=pixel[c];
            }
            unsigned char *pixel=dst+((size_t)y*width+x)*4;
            for (unsigned int c=0;c<3;c++) pixel[c]=(unsigned char)((rgb[c]+area/2)/area);
            pixel[3]=255;
        }
        return 1;
    }
    unsigned int radius=kernel==DELI_BOX ? 0 : kernel==DELI_LANCZOS3 ? 3 : 2;
    unsigned int taps=(radius*2+1)*scale;
    double weights[28], sum=0;
    for (unsigned int k=0;k<taps;k++) {
        weights[k]=weight(((double)k+0.5)/scale-radius-0.5,kernel);
        sum+=weights[k];
    }
    for (unsigned int k=0;k<taps;k++) weights[k]/=sum;
    float *horizontal=malloc((size_t)width*height*3*sizeof(float));
    if (!horizontal) return 0;
    for (unsigned int y=0;y<height;y++) for (unsigned int x=0;x<width;x++) {
        double rgb[3]={0,0,0};
        for (unsigned int k=0;k<taps;k++) {
            unsigned int sx=clamp((int64_t)x*scale+k-radius*scale,width*scale);
            const unsigned char *pixel=src+((size_t)y*width*scale+sx)*4;
            for (unsigned int c=0;c<3;c++) rgb[c]+=weights[k]*pixel[c];
        }
        for (unsigned int c=0;c<3;c++) horizontal[((size_t)y*width+x)*3+c]=(float)rgb[c];
    }
    for (unsigned int y=0;y<rows;y++) for (unsigned int x=0;x<width;x++) {
        double rgb[3]={0,0,0};
        for (unsigned int k=0;k<taps;k++) {
            unsigned int sy=clamp((int64_t)(top+y)*scale+k-radius*scale,height);
            const float *pixel=horizontal+((size_t)sy*width+x)*3;
            for (unsigned int c=0;c<3;c++) rgb[c]+=weights[k]*pixel[c];
        }
        unsigned char *pixel=dst+((size_t)y*width+x)*4;
        for (unsigned int c=0;c<3;c++) pixel[c]=(unsigned char)lround(fmin(255,fmax(0,rgb[c])));
        pixel[3]=255;
    }
    free(horizontal); return 1;
}
