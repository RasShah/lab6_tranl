%code requires {
    #include "ast.h"
}

%{
#include "ast.h"
int yylex(void);
void yyerror(const char *message);
%}

%define parse.error detailed
%define parse.lac full
%locations
%expect 0

%union {
    Node *node;
    const char *text;
}

%token INT "int" BOOL "bool"
%token <node> IDENTIFIER "identifier" INTEGER "integer" BOOLEAN "boolean"
%token OR "||" AND "&&" EQ "==" NE "!=" LE "<=" GE ">="
%token INVALID "invalid token"
%type <node> program declarations declaration variables variable expression
%type <text> type

%left OR
%left AND
%left EQ NE
%left '<' '>' LE GE
%left '+' '-'
%left '*' '/' '%'
%precedence UNARY

%start program

%%

program:
    declarations { program_root = $1; $$ = $1; }
;

declarations:
    declaration { $$ = node_add(node_new("Program", "", 1, 1), $1); program_root = $$; }
  | declarations declaration { $$ = node_add($1, $2); }
  | error ';' { $$ = node_new("Program", "", 1, 1); program_root = $$; yyerrok; }
  | declarations error ';' { $$ = $1; yyerrok; }
;

declaration:
    type variables ';' {
        $$ = node_new("Declaration", $1, @1.first_line, @1.first_column);
        node_add($$, $2);
    }
;

type:
    INT { $$ = "int"; }
  | BOOL { $$ = "bool"; }
;

variables:
    variable { $$ = node_add(node_new("Variables", "", @1.first_line, @1.first_column), $1); }
  | variables ',' variable { $$ = node_add($1, $3); }
;

variable:
    IDENTIFIER {
        $$ = node_new("Variable", $1->value, @1.first_line, @1.first_column);
    }
  | IDENTIFIER '=' expression {
        $$ = node_add(node_new("Variable", $1->value, @1.first_line, @1.first_column), $3);
    }
;

expression:
    INTEGER { $$ = $1; }
  | BOOLEAN { $$ = $1; }
  | IDENTIFIER { $$ = $1; }
  | '(' expression ')' { $$ = node_add(node_new("Group", "()", @1.first_line, @1.first_column), $2); }
  | '+' expression %prec UNARY { $$ = node_unary("+", $2, @1.first_line, @1.first_column); }
  | '-' expression %prec UNARY { $$ = node_unary("-", $2, @1.first_line, @1.first_column); }
  | '!' expression %prec UNARY { $$ = node_unary("!", $2, @1.first_line, @1.first_column); }
  | expression '+' expression { $$ = node_binary("+", $1, $3, @2.first_line, @2.first_column); }
  | expression '-' expression { $$ = node_binary("-", $1, $3, @2.first_line, @2.first_column); }
  | expression '*' expression { $$ = node_binary("*", $1, $3, @2.first_line, @2.first_column); }
  | expression '/' expression { $$ = node_binary("/", $1, $3, @2.first_line, @2.first_column); }
  | expression '%' expression { $$ = node_binary("%", $1, $3, @2.first_line, @2.first_column); }
  | expression '<' expression { $$ = node_binary("<", $1, $3, @2.first_line, @2.first_column); }
  | expression '>' expression { $$ = node_binary(">", $1, $3, @2.first_line, @2.first_column); }
  | expression LE expression { $$ = node_binary("<=", $1, $3, @2.first_line, @2.first_column); }
  | expression GE expression { $$ = node_binary(">=", $1, $3, @2.first_line, @2.first_column); }
  | expression EQ expression { $$ = node_binary("==", $1, $3, @2.first_line, @2.first_column); }
  | expression NE expression { $$ = node_binary("!=", $1, $3, @2.first_line, @2.first_column); }
  | expression AND expression { $$ = node_binary("&&", $1, $3, @2.first_line, @2.first_column); }
  | expression OR expression { $$ = node_binary("||", $1, $3, @2.first_line, @2.first_column); }
;

%%

void yyerror(const char *message) {
    record_error("syntax", message, yylloc.first_line, yylloc.first_column);
}
