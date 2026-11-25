#include "ast.h"
#include <stdio.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

int yyparse(void);
int yylex(void);
int yylex_destroy(void);

int main(void) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
#endif
    int status = yyparse();
    while (yylex() != 0) {}
    print_report();
    int failed = status != 0 || diagnostic_count != 0;
    yylex_destroy();
    free_report();
    return failed ? 1 : 0;
}
