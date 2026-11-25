#ifndef ANALYZER_AST_H
#define ANALYZER_AST_H

#include <stddef.h>

typedef struct Node {
    size_t id;
    const char *kind;
    char *value;
    int line, column;
    struct Node **children;
    size_t count, capacity;
} Node;

extern Node *program_root;
extern int diagnostic_count;

Node *node_new(const char *kind, const char *value, int line, int column);
Node *node_add(Node *parent, Node *child);
Node *node_unary(const char *op, Node *operand, int line, int column);
Node *node_binary(const char *op, Node *left, Node *right, int line, int column);
void record_token(const char *kind, const char *text, int line, int column);
void record_error(const char *stage, const char *message, int line, int column);
void print_report(void);
void free_report(void);

#endif
