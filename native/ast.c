#include "ast.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *kind; char *text; int line, column; } Token;
typedef struct { const char *stage; char *message; int line, column; } Diagnostic;

Node *program_root = NULL;
int diagnostic_count = 0;
static Node **nodes = NULL;
static size_t node_count = 0, node_capacity = 0;
static Token *tokens = NULL;
static size_t token_count = 0, token_capacity = 0;
static Diagnostic *diagnostics = NULL;
static size_t diagnostic_capacity = 0;

static void *checked_realloc(void *ptr, size_t size) {
    void *result = realloc(ptr, size);
    if (!result) { fputs("Not enough memory\n", stderr); exit(2); }
    return result;
}

static char *copy_string(const char *text) {
    size_t length = strlen(text) + 1;
    char *result = checked_realloc(NULL, length);
    memcpy(result, text, length);
    return result;
}

#define GROW(array, count, capacity) do { \
    if ((count) == (capacity)) { \
        (capacity) = (capacity) ? (capacity) * 2 : 16; \
        (array) = checked_realloc((array), (capacity) * sizeof(*(array))); \
    } \
} while (0)

Node *node_new(const char *kind, const char *value, int line, int column) {
    Node *node = checked_realloc(NULL, sizeof(*node));
    *node = (Node){node_count, kind, copy_string(value), line, column, NULL, 0, 0};
    GROW(nodes, node_count, node_capacity);
    nodes[node_count++] = node;
    return node;
}

Node *node_add(Node *parent, Node *child) {
    GROW(parent->children, parent->count, parent->capacity);
    parent->children[parent->count++] = child;
    return parent;
}

Node *node_unary(const char *op, Node *operand, int line, int column) {
    return node_add(node_new("Unary", op, line, column), operand);
}

Node *node_binary(const char *op, Node *left, Node *right, int line, int column) {
    return node_add(node_add(node_new("Binary", op, line, column), left), right);
}

void record_token(const char *kind, const char *text, int line, int column) {
    GROW(tokens, token_count, token_capacity);
    tokens[token_count++] = (Token){kind, copy_string(text), line, column};
}

void record_error(const char *stage, const char *message, int line, int column) {
    GROW(diagnostics, (size_t)diagnostic_count, diagnostic_capacity);
    diagnostics[diagnostic_count++] = (Diagnostic){stage, copy_string(message), line, column};
}

static void json_string(const char *text) {
    putchar('"');
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        switch (*p) {
            case '"': fputs("\\\"", stdout); break;
            case '\\': fputs("\\\\", stdout); break;
            case '\n': fputs("\\n", stdout); break;
            case '\r': fputs("\\r", stdout); break;
            case '\t': fputs("\\t", stdout); break;
            default:
                if (*p < 0x20) printf("\\u%04x", *p);
                else putchar(*p);
        }
    }
    putchar('"');
}

void print_report(void) {
    printf("{\"backend\":\"GNU Bison + Flex\",\"root\":");
    if (program_root) printf("%zu", program_root->id); else fputs("null", stdout);
    fputs(",\"nodes\":[", stdout);
    for (size_t i = 0; i < node_count; ++i) {
        Node *node = nodes[i];
        if (i) putchar(',');
        printf("{\"id\":%zu,\"kind\":", node->id); json_string(node->kind);
        fputs(",\"value\":", stdout); json_string(node->value);
        printf(",\"line\":%d,\"column\":%d,\"children\":[", node->line, node->column);
        for (size_t j = 0; j < node->count; ++j) {
            if (j) putchar(',');
            printf("%zu", node->children[j]->id);
        }
        fputs("]}", stdout);
    }
    fputs("],\"tokens\":[", stdout);
    for (size_t i = 0; i < token_count; ++i) {
        Token *token = &tokens[i];
        if (i) putchar(',');
        fputs("{\"kind\":", stdout); json_string(token->kind);
        fputs(",\"text\":", stdout); json_string(token->text);
        printf(",\"line\":%d,\"column\":%d}", token->line, token->column);
    }
    fputs("],\"diagnostics\":[", stdout);
    for (int i = 0; i < diagnostic_count; ++i) {
        Diagnostic *d = &diagnostics[i];
        if (i) putchar(',');
        fputs("{\"stage\":", stdout); json_string(d->stage);
        fputs(",\"message\":", stdout); json_string(d->message);
        printf(",\"line\":%d,\"column\":%d}", d->line, d->column);
    }
    fputs("]}\n", stdout);
}

void free_report(void) {
    for (size_t i = 0; i < node_count; ++i) {
        free(nodes[i]->value); free(nodes[i]->children); free(nodes[i]);
    }
    for (size_t i = 0; i < token_count; ++i) free(tokens[i].text);
    for (int i = 0; i < diagnostic_count; ++i) free(diagnostics[i].message);
    free(nodes); free(tokens); free(diagnostics);
}
