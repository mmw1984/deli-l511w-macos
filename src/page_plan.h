#ifndef DELI_PAGE_PLAN_H
#define DELI_PAGE_PLAN_H
#include <stddef.h>
typedef struct { unsigned int *pages; size_t count; } DeliPlan;
/* Page numbers are one-based; zero denotes a blank sheet side. */
int deli_page_plan(unsigned int total, const char *ranges, const char *page_set,
                   const char *order, const char *manual, const char *pass2,
                   int default_reverse, DeliPlan *plan, char *error, size_t error_size);
#endif
