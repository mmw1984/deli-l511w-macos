#include <jni.h>
#include "deli.c"

typedef struct {
    FILE *file;
    const Paper *paper;
    unsigned int width, height, y, copies, media;
    int gray, page_open, finished;
} Encoder;
static _Thread_local jmp_buf fault;
static _Thread_local char error_text[256];
static void bridge_error(const char *message) {
    snprintf(error_text,sizeof(error_text),"%s",message);
    longjmp(fault,1);
}
static void exception(JNIEnv *env) {
    (*env)->ThrowNew(env,(*env)->FindClass(env,"java/io/IOException"),error_text);
}
#define GUARD(value) deli_error_handler=bridge_error; if (setjmp(fault)) { exception(env); return value; }
static Encoder *context(jlong handle) {
    if (!handle) fail("Encoder is closed");
    Encoder *encoder=(Encoder *)(intptr_t)handle;
    if (encoder->finished) fail("Encoder is finished");
    deli_output=encoder->file;
    return encoder;
}
static void string(JNIEnv *env, jstring value, char *buffer, size_t capacity) {
    if (!value || (*env)->GetStringUTFLength(env,value)>=(jsize)capacity) fail("Invalid encoder option");
    const char *text=(*env)->GetStringUTFChars(env,value,NULL);
    if (!text) fail("Cannot read encoder option");
    snprintf(buffer,capacity,"%s",text);
    (*env)->ReleaseStringUTFChars(env,value,text);
}
JNIEXPORT jlong JNICALL Java_com_deli_print_NativeEncoder_begin(JNIEnv *env, jobject self,
        jint fd, jstring paper_name, jint media, jstring quality, jboolean gray, jint copies, jstring title) {
    (void)self;
    Encoder *encoder=calloc(1,sizeof(*encoder));
    if (!encoder) { snprintf(error_text,sizeof(error_text),"Out of memory"); exception(env); return 0; }
    deli_error_handler=bridge_error;
    if (setjmp(fault)) {
        if (encoder->file) fclose(encoder->file);
        free(encoder); exception(env); return 0;
    }
    char name[64], q[32], job_title[1024];
    string(env,paper_name,name,sizeof(name)); string(env,quality,q,sizeof(q)); string(env,title,job_title,sizeof(job_title));
    for (size_t i=0;i<sizeof(papers)/sizeof(*papers);i++)
        if (!strcmp(name,papers[i].option)) encoder->paper=&papers[i];
    if (!encoder->paper || copies<1 || copies>65535) fail("Invalid paper or copies");
    if (strcmp(q,"NORMAL") && strcmp(q,"HIGH") && strcmp(q,"DRAFT")) fail("Invalid quality");
    if (media && media!=0xff && media!=0xdc && media!=0xdd && media!=0xf7 && media!=0xf6) fail("Invalid media");
    encoder->media=media ? (unsigned int)media : encoder->paper->media;
    if (encoder->media==0xdd && !strcmp(q,"DRAFT")) strcpy(q,"NORMAL");
    encoder->copies=(unsigned int)copies; encoder->gray=gray;
    unsigned int pw,ph;
    deli_geometry(encoder->paper,&encoder->width,&encoder->height,&pw,&ph);
    int duplicate=dup(fd);
    if (duplicate<0) fail("Cannot duplicate output fd");
    encoder->file=fdopen(duplicate,"wb");
    if (!encoder->file) { close(duplicate); fail("Cannot open output fd"); }
    deli_output=encoder->file;
    job_start("Android",job_title,q,gray);
    return (jlong)(intptr_t)encoder;
}
JNIEXPORT void JNICALL Java_com_deli_print_NativeEncoder_startPage(JNIEnv *env,jobject self,jlong handle) {
    (void)self; GUARD(); Encoder *encoder=context(handle);
    if (encoder->page_open) fail("Page already open");
    encoder->y=0; encoder->page_open=1;
    page_start(encoder->paper,encoder->media,90,encoder->gray,encoder->copies);
}
JNIEXPORT void JNICALL Java_com_deli_print_NativeEncoder_push(JNIEnv *env,jobject self,jlong handle,jintArray pixels,jint width,jint rows) {
    (void)self;
    unsigned char *volatile buffer=NULL;
    deli_error_handler=bridge_error;
    if (setjmp(fault)) { free(buffer); exception(env); return; }
    Encoder *encoder=context(handle);
    if (!encoder->page_open || width!=(jint)encoder->width || rows<1 || rows>256 ||
        encoder->y+(unsigned int)rows>encoder->height ||
        (rows!=256 && encoder->y+(unsigned int)rows!=encoder->height) ||
        !pixels || (*env)->GetArrayLength(env,pixels)!=width*rows) fail("Invalid band geometry");
    buffer=malloc((size_t)width*rows*3);
    if (!buffer) fail("Out of memory");
    jint *argb=(*env)->GetIntArrayElements(env,pixels,NULL);
    if (!argb) { free(buffer); return; }
    for (int i=0;i<width*rows;i++) {
        buffer[i*3]=(unsigned int)argb[i]>>16;
        buffer[i*3+1]=(unsigned int)argb[i]>>8;
        buffer[i*3+2]=(unsigned int)argb[i];
    }
    (*env)->ReleaseIntArrayElements(env,pixels,argb,JNI_ABORT);
    if (encoder->gray) deli_mono(buffer,buffer,(unsigned int)(width*rows),0);
    band(buffer,(unsigned int)width,(unsigned int)rows,encoder->y,encoder->gray,90);
    encoder->y+=(unsigned int)rows;
    free(buffer);
}
JNIEXPORT void JNICALL Java_com_deli_print_NativeEncoder_endPage(JNIEnv *env,jobject self,jlong handle) {
    (void)self; GUARD(); Encoder *encoder=context(handle);
    if (!encoder->page_open || encoder->y!=encoder->height) fail("Incomplete page");
    deli_page_end(encoder->copies); encoder->page_open=0;
}
JNIEXPORT void JNICALL Java_com_deli_print_NativeEncoder_finish(JNIEnv *env,jobject self,jlong handle) {
    (void)self; GUARD(); Encoder *encoder=context(handle);
    if (encoder->page_open) fail("Incomplete page");
    deli_job_end(); encoder->finished=1;
}
JNIEXPORT void JNICALL Java_com_deli_print_NativeEncoder_close(JNIEnv *env,jobject self,jlong handle) {
    (void)env; (void)self;
    Encoder *encoder=(Encoder *)(intptr_t)handle;
    if (encoder) { fclose(encoder->file); free(encoder); }
}
JNIEXPORT jintArray JNICALL Java_com_deli_print_NativeEncoder_plan(JNIEnv *env,jobject self,jint total,jstring ranges,jstring duplex,jstring pass2) {
    (void)self; GUARD(NULL);
    char range_text[8192], manual[32], order[32], error[128];
    if (ranges) string(env,ranges,range_text,sizeof(range_text));
    string(env,duplex,manual,sizeof(manual)); string(env,pass2,order,sizeof(order));
    DeliPlan plan;
    if (!deli_page_plan((unsigned int)total,ranges ? range_text : NULL,NULL,NULL,manual,order,1,&plan,error,sizeof(error))) fail(error);
    jintArray result=(*env)->NewIntArray(env,(jsize)plan.count);
    if (result) (*env)->SetIntArrayRegion(env,result,0,(jsize)plan.count,(const jint *)plan.pages);
    free(plan.pages); return result;
}
