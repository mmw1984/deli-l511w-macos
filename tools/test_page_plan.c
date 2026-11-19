#include "page_plan.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static DeliPlan make(unsigned int n, const char *range, const char *set,
                     const char *order, const char *manual, const char *pass2, int reverse) {
    DeliPlan p; char error[128];
    assert(deli_page_plan(n,range,set,order,manual,pass2,reverse,&p,error,sizeof(error)));
    return p;
}
int main(void) {
    const char *orders[]={"Auto","Reverse","Normal"};
    for (unsigned int n=1;n<=7;n++) {
        for (int reverse=0;reverse<=1;reverse++) {
            for (int mode=1;mode<=2;mode++) for (int o=0;o<3;o++) {
                DeliPlan p=make(n,NULL,NULL,NULL,mode==1 ? "Odd" : "Even",orders[o],reverse);
                assert(p.count==(n+1)/2);
                int rev=mode==2 && o ? o==1 : reverse;
                for (size_t i=0;i<p.count;i++) {
                    size_t sheet=rev ? p.count-1-i : i;
                    unsigned int expected=(unsigned int)(2*sheet+mode);
                    if (expected>n) expected=0;
                    assert(p.pages[i]==expected);
                }
                free(p.pages);
            }
        }
        for (int mode=0;mode<2;mode++) {
            DeliPlan p=make(n,NULL,NULL,mode ? "reverse" : "normal","Off",NULL,!mode);
            assert(p.count==n);
            for (unsigned int i=0;i<n;i++) assert(p.pages[i]==(mode ? n-i : i+1));
            free(p.pages);
        }
        printf("PASS: page plan %u pages: both duplex passes, Auto/Reverse/Normal, both front orders\n",n);
    }
    DeliPlan p=make(7,"2-4,6-","even","normal","Off",NULL,1);
    assert(p.count==3 && p.pages[0]==2 && p.pages[1]==4 && p.pages[2]==6); free(p.pages);
    p=make(5,"2-4",NULL,NULL,"Odd","Auto",1);
    assert(p.count==2 && p.pages[0]==3 && p.pages[1]==0); free(p.pages);
    p=make(5,"2-4",NULL,NULL,"Even","Auto",1);
    assert(p.count==2 && p.pages[0]==4 && p.pages[1]==2); free(p.pages);
    p=make(2,"9-10",NULL,NULL,NULL,NULL,1); assert(!p.count); free(p.pages);
    p=make(7,"1-7,2-5","odd",NULL,NULL,NULL,1);
    assert(p.count==4 && p.pages[0]==7 && p.pages[3]==1); free(p.pages);
    char error[128]; const char *bad[]={"","0","2-1","1,","a","-2","4294967296","1--3"};
    for (size_t i=0;i<sizeof(bad)/sizeof(*bad);i++)
        assert(!deli_page_plan(7,bad[i],NULL,NULL,NULL,NULL,1,&p,error,sizeof(error)));
    assert(!deli_page_plan(0,NULL,NULL,NULL,NULL,NULL,1,&p,error,sizeof(error)));
    assert(!deli_page_plan(7,NULL,"bogus",NULL,NULL,NULL,1,&p,error,sizeof(error)));
    assert(!deli_page_plan(7,NULL,NULL,"bogus",NULL,NULL,1,&p,error,sizeof(error)));
    assert(!deli_page_plan(7,NULL,NULL,NULL,"bogus",NULL,1,&p,error,sizeof(error)));
    assert(!deli_page_plan(7,NULL,NULL,NULL,NULL,"bogus",1,&p,error,sizeof(error)));
    puts("PASS: ranges/unions/open ranges/parity, blank alignment, empty selection and invalid options");
    puts("ALL PAGE PLAN TESTS PASSED");
    return 0;
}
