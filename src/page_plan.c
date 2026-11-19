#include "page_plan.h"
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int number(const char **text, unsigned int *value) {
    const char *p=*text;
    if (*p<'0' || *p>'9') return 0;
    unsigned int n=0;
    do {
        unsigned int digit=(unsigned int)(*p++-'0');
        if (n>(UINT_MAX-digit)/10) return 0;
        n=n*10+digit;
    } while (*p>='0' && *p<='9');
    if (!n) return 0;
    *text=p; *value=n; return 1;
}

int deli_page_plan(unsigned int total, const char *ranges, const char *page_set,
                   const char *order, const char *manual, const char *pass2,
                   int default_reverse, DeliPlan *plan, char *error, size_t error_size) {
    const char *message="Invalid page selection/order option";
    unsigned char *selected=NULL;
    plan->pages=NULL; plan->count=0;
    if (!total || total>1000000) goto bad;
    int mode=0, reverse=default_reverse, second=-1, parity=0;
    if (manual && strcmp(manual,"Off")) {
        if (!strcmp(manual,"Odd")) mode=1;
        else if (!strcmp(manual,"Even")) mode=2;
        else goto bad;
    }
    if (page_set && strcmp(page_set,"all")) {
        if (!strcmp(page_set,"odd")) parity=1;
        else if (!strcmp(page_set,"even")) parity=2;
        else goto bad;
    }
    if (order) {
        if (!strcmp(order,"reverse") || !strcmp(order,"Reverse")) reverse=1;
        else if (!strcmp(order,"normal") || !strcmp(order,"Normal")) reverse=0;
        else goto bad;
    }
    if (pass2 && strcmp(pass2,"Auto")) {
        if (!strcmp(pass2,"Reverse")) second=1;
        else if (!strcmp(pass2,"Normal")) second=0;
        else goto bad;
    }
    selected=calloc((size_t)total+2,1);
    plan->pages=malloc(((size_t)total+1)*sizeof(*plan->pages));
    if (!selected || !plan->pages) { message="Out of memory"; goto bad; }
    if (!ranges) memset(selected+1,1,total);
    else {
        const char *p=ranges;
        do {
            unsigned int first,last;
            if (!number(&p,&first)) goto bad;
            last=first;
            if (*p=='-') {
                p++;
                if (!*p || *p==',') last=UINT_MAX;
                else if (!number(&p,&last)) goto bad;
            }
            if (last<first || (*p && *p!=',')) goto bad;
            if (last>total) last=total;
            for (unsigned int n=first;n<=last;n++) selected[n]=1;
            if (!*p) break;
            if (!*++p) goto bad;
        } while (1);
    }
    for (unsigned int n=1;n<=total;n++)
        if ((parity==1 && !(n&1)) || (parity==2 && (n&1))) selected[n]=0;
    if (!mode) {
        for (unsigned int n=1;n<=total;n++)
            if (selected[n]) plan->pages[plan->count++]=n;
    } else {
        for (unsigned int n=1;n<=total;n+=2) {
            if (!selected[n] && !selected[n+1]) continue;
            unsigned int side=mode==1 ? n : n+1;
            plan->pages[plan->count++]=selected[side] ? side : 0;
        }
        if (mode==2 && second!=-1) reverse=second;
        /* Auto follows the front pass order: turning the stack reverses feed order. */
    }
    if (reverse)
        for (size_t i=0;i<plan->count/2;i++) {
            unsigned int n=plan->pages[i];
            plan->pages[i]=plan->pages[plan->count-1-i];
            plan->pages[plan->count-1-i]=n;
        }
    free(selected); return 1;
bad:
    free(selected); free(plan->pages); plan->pages=NULL; plan->count=0;
    snprintf(error,error_size,"%s",message); return 0;
}
