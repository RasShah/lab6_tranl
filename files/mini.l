%option noyywrap nounput noinput nodefault never-interactive
%x COMMENT

%{
#include "parser.h"
#include "ast.h"

static int current_line = 1, current_column = 1;
static int comment_line = 1, comment_column = 1;

static void locate(const char *text, int length) {
    yylloc.first_line = current_line;
    yylloc.first_column = current_column;
    for (int i = 0; i < length; ++i) {
        yylloc.last_line = current_line;
        yylloc.last_column = current_column;
        unsigned char c = (unsigned char)text[i];
        if (c == '\n') { ++current_line; current_column = 1; }
        else if ((c & 0xc0) != 0x80) { ++current_column; }
    }
}

#define YY_USER_ACTION locate(yytext, yyleng);
#define TOKEN(kind, token) do { record_token(kind, yytext, yylloc.first_line, yylloc.first_column); return token; } while (0)
#define LEAF(kind, token, node_kind) do { \
    yylval.node = node_new(node_kind, yytext, yylloc.first_line, yylloc.first_column); \
    TOKEN(kind, token); \
} while (0)
%}

%%

[ \t\r\n]+                 {}
"//"[^\n]*                 {}
"/*"                       { comment_line = yylloc.first_line; comment_column = yylloc.first_column; BEGIN(COMMENT); }
<COMMENT>"*/"              { BEGIN(INITIAL); }
<COMMENT>[^*\n]+           {}
<COMMENT>"*"               {}
<COMMENT>\n                {}
<COMMENT><<EOF>>           {
    record_error("lexical", "Unterminated block comment", comment_line, comment_column);
    BEGIN(INITIAL);
    return 0;
}

"int"                      { TOKEN("INT", INT); }
"bool"                     { TOKEN("BOOL", BOOL); }
"TRUE"|"FALSE"             { LEAF("BOOLEAN", BOOLEAN, "Boolean"); }
[0-9]+[a-zA-Z][a-zA-Z0-9]* {
    record_error("lexical", "Identifier cannot start with a digit", yylloc.first_line, yylloc.first_column);
    TOKEN("INVALID", INVALID);
}
[0-9]+                     { LEAF("INTEGER", INTEGER, "Integer"); }
[a-zA-Z][a-zA-Z0-9]*       { LEAF("VAR", IDENTIFIER, "Identifier"); }
"||"                       { TOKEN("OR", OR); }
"&&"                       { TOKEN("AND", AND); }
"=="                       { TOKEN("EQ", EQ); }
"!="                       { TOKEN("NE", NE); }
"<="                       { TOKEN("LE", LE); }
">="                       { TOKEN("GE", GE); }
"="                        { TOKEN("ASSIGN", '='); }
"+"                        { TOKEN("PLUS", '+'); }
"-"                        { TOKEN("MINUS", '-'); }
"*"                        { TOKEN("STAR", '*'); }
"/"                        { TOKEN("SLASH", '/'); }
"%"                        { TOKEN("PERCENT", '%'); }
"!"                        { TOKEN("NOT", '!'); }
"<"                        { TOKEN("LT", '<'); }
">"                        { TOKEN("GT", '>'); }
"("                        { TOKEN("LPAREN", '('); }
")"                        { TOKEN("RPAREN", ')'); }
","                        { TOKEN("COMMA", ','); }
";"                        { TOKEN("SEMICOLON", ';'); }
[\xC2-\xDF][\x80-\xBF]|[\xE0-\xEF][\x80-\xBF]{2}|[\xF0-\xF4][\x80-\xBF]{3}|. {
    record_error("lexical", "Unexpected character", yylloc.first_line, yylloc.first_column);
    TOKEN("INVALID", INVALID);
}
<<EOF>> {
    yylloc.first_line = yylloc.last_line = current_line;
    yylloc.first_column = yylloc.last_column = current_column;
    return 0;
}

%%
