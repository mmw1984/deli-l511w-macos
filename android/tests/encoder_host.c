#include "deli.c"

int main(int argc, char **argv) {
    if (argc<9) return 1;
    unsigned int w=(unsigned int)atoi(argv[1]), h=(unsigned int)atoi(argv[2]);
    int inputgray=atoi(argv[3]), gray=atoi(argv[4]);
    const Paper *paper=NULL;
    for (size_t i=0;i<sizeof(papers)/sizeof(*papers);i++)
        if (!strcmp(argv[5],papers[i].option)) paper=&papers[i];
    if (!w || !h || w>65535 || h>65535 || !paper) return 1;
    unsigned int media=(unsigned int)strtoul(argv[6],NULL,0);
    unsigned int channels=inputgray ? 1u : 3u;
    unsigned char *source=malloc((size_t)w*256*channels);
    unsigned char *pixels=malloc((size_t)w*256*(gray ? 1u : 3u));
    if (!source || !pixels) return 1;
    deli_output=stdout;
    job_start("Android","host",argv[7],gray);
    for (int i=8;i<argc;i++) {
        FILE *file=fopen(argv[i],"rb"); if (!file) return 1;
        page_start(paper,media,90,gray,1);
        for (unsigned int y=0;y<h;) {
            unsigned int rows=h-y; if (rows>256) rows=256;
            size_t size=(size_t)w*rows*channels;
            if (fread(source,1,size,file)!=size) return 1;
            if (gray) deli_mono(pixels,source,w*rows,inputgray);
            else memcpy(pixels,source,size);
            band(pixels,w,rows,y,gray,90); y+=rows;
        }
        if (fgetc(file)!=EOF) return 1;
        fclose(file); deli_page_end(1);
    }
    deli_job_end(); free(source); free(pixels); return 0;
}
