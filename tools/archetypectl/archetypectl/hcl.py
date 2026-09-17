"""A tolerant, dependency-free reader for the slice of HCL that Terramate uses.

This is **not** a general HCL implementation and does not try to be. It reads
blocks, labels and attributes, and evaluates the literal subset of expressions
(strings with interpolation, numbers, bools, lists, objects, traversals).
Anything it cannot evaluate comes back as ``UNRESOLVED`` rather than as a
guess -- the enricher then reports the raw expression and the policy decides.

Guessing is the failure mode that matters here: an ordering invariant checked
against a value we invented is worse than no check at all.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple


class HCLError(ValueError):
    """Raised when a file cannot be read as the HCL subset."""


class _Unresolved:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNRESOLVED"

    def __bool__(self) -> bool:
        return False


UNRESOLVED = _Unresolved()

_IDENT_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_CHARS = _IDENT_START | set("0123456789-")
_DIGITS = set("0123456789")
_OPERATORS = ("...", "==", "!=", "<=", ">=", "&&", "||", "=>")
_PUNCT = set("{}[](),.=+-*/%!<>&|?:")


class Token:
    """One lexical token. ``raw`` is the exact source slice, for round-tripping."""

    __slots__ = ("kind", "value", "raw", "line", "parts")

    def __init__(
        self,
        kind: str,
        value: Any,
        raw: str,
        line: int,
        parts: Optional[List[Any]] = None,
    ) -> None:
        self.kind = kind  # IDENT | STRING | NUMBER | HEREDOC | PUNCT | NEWLINE | EOF
        self.value = value
        self.raw = raw
        self.line = line
        # For STRING: the interpolation segments -- str literals and Expr holes.
        self.parts = parts

    def is_punct(self, text: str) -> bool:
        return self.kind == "PUNCT" and self.value == text

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Token(%s, %r, line=%d)" % (self.kind, self.value, self.line)


class Expr:
    """An attribute value, kept as tokens plus the raw source text."""

    __slots__ = ("tokens", "raw", "line")

    def __init__(self, tokens: List[Token], raw: str, line: int) -> None:
        self.tokens = tokens
        self.raw = raw
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Expr(%r)" % (self.raw,)


class Block:
    __slots__ = ("type", "labels", "body", "line")

    def __init__(self, type_: str, labels: List[str], body: "Body", line: int) -> None:
        self.type = type_
        self.labels = labels
        self.body = body
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Block(%s, %r)" % (self.type, self.labels)


class Body:
    __slots__ = ("attributes", "blocks")

    def __init__(self) -> None:
        self.attributes: Dict[str, Expr] = {}
        self.blocks: List[Block] = []

    def of_type(self, *types: str) -> Iterator[Block]:
        for block in self.blocks:
            if block.type in types:
                yield block


# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------


def tokenize(src: str, filename: str = "<string>") -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    n = len(src)

    while i < n:
        ch = src[i]

        if ch == "\n":
            tokens.append(Token("NEWLINE", "\n", "\n", line))
            line += 1
            i += 1
            continue

        if ch in " \t\r":
            i += 1
            continue

        # Comments -------------------------------------------------------
        if ch == "#" or (ch == "/" and src.startswith("//", i)):
            end = src.find("\n", i)
            i = n if end == -1 else end
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            if end == -1:
                raise HCLError("%s:%d: unterminated block comment" % (filename, line))
            line += src.count("\n", i, end)
            i = end + 2
            continue

        # Heredoc --------------------------------------------------------
        if src.startswith("<<", i):
            token, i, line = _read_heredoc(src, i, line, filename)
            tokens.append(token)
            continue

        # String ---------------------------------------------------------
        if ch == '"':
            token, i, line = _read_string(src, i, line, filename)
            tokens.append(token)
            continue

        # Number ---------------------------------------------------------
        if ch in _DIGITS:
            start = i
            while i < n and (src[i] in _DIGITS or src[i] == "."):
                i += 1
            if i < n and src[i] in "eE":
                j = i + 1
                if j < n and src[j] in "+-":
                    j += 1
                if j < n and src[j] in _DIGITS:
                    i = j
                    while i < n and src[i] in _DIGITS:
                        i += 1
            raw = src[start:i]
            value: Any
            try:
                value = int(raw) if ("." not in raw and "e" not in raw.lower()) else float(raw)
            except ValueError:
                value = raw
            tokens.append(Token("NUMBER", value, raw, line))
            continue

        # Identifier -----------------------------------------------------
        if ch in _IDENT_START:
            start = i
            while i < n and src[i] in _IDENT_CHARS:
                i += 1
            raw = src[start:i]
            tokens.append(Token("IDENT", raw, raw, line))
            continue

        # Punctuation ----------------------------------------------------
        matched = False
        for op in _OPERATORS:
            if src.startswith(op, i):
                tokens.append(Token("PUNCT", op, op, line))
                i += len(op)
                matched = True
                break
        if matched:
            continue

        if ch in _PUNCT:
            tokens.append(Token("PUNCT", ch, ch, line))
            i += 1
            continue

        raise HCLError("%s:%d: unexpected character %r" % (filename, line, ch))

    tokens.append(Token("EOF", None, "", line))
    return tokens


def _read_heredoc(src: str, i: int, line: int, filename: str) -> Tuple[Token, int, int]:
    start = i
    j = i + 2
    if j < len(src) and src[j] == "-":
        j += 1
    marker_start = j
    while j < len(src) and src[j] in _IDENT_CHARS:
        j += 1
    marker = src[marker_start:j]
    if not marker:
        raise HCLError("%s:%d: heredoc without a marker" % (filename, line))
    nl = src.find("\n", j)
    if nl == -1:
        raise HCLError("%s:%d: unterminated heredoc %s" % (filename, line, marker))
    body_start = nl + 1
    pos = body_start
    while True:
        end_of_line = src.find("\n", pos)
        chunk = src[pos:] if end_of_line == -1 else src[pos:end_of_line]
        if chunk.strip() == marker:
            raw = src[start : (len(src) if end_of_line == -1 else end_of_line)]
            value = src[body_start:pos]
            return (
                Token("HEREDOC", value, raw, line),
                len(src) if end_of_line == -1 else end_of_line,
                line + raw.count("\n"),
            )
        if end_of_line == -1:
            raise HCLError("%s:%d: unterminated heredoc %s" % (filename, line, marker))
        pos = end_of_line + 1


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}


def _read_string(src: str, i: int, line: int, filename: str) -> Tuple[Token, int, int]:
    """Read a quoted string, splitting out ``${...}`` interpolation holes."""
    start = i
    start_line = line
    i += 1
    literal: List[str] = []
    parts: List[Any] = []
    n = len(src)

    while i < n:
        ch = src[i]
        if ch == "\\":
            if i + 1 >= n:
                raise HCLError("%s:%d: unterminated string" % (filename, start_line))
            nxt = src[i + 1]
            if nxt in _ESCAPES:
                literal.append(_ESCAPES[nxt])
                i += 2
                continue
            if nxt == "u":
                literal.append(chr(int(src[i + 2 : i + 6], 16)))
                i += 6
                continue
            literal.append(nxt)
            i += 2
            continue
        if ch == '"':
            i += 1
            if literal:
                parts.append("".join(literal))
            raw = src[start:i]
            simple = len(parts) == 1 and isinstance(parts[0], str)
            value = parts[0] if simple else ("" if not parts else None)
            return Token("STRING", value, raw, start_line, parts), i, line
        if src.startswith("${", i) or src.startswith("%{", i):
            directive = src[i] == "%"
            end = _match_brace(src, i + 1)
            if end == -1:
                raise HCLError(
                    "%s:%d: unterminated interpolation in string" % (filename, start_line)
                )
            if literal:
                parts.append("".join(literal))
                literal = []
            inner = src[i + 2 : end]
            if directive:
                # %{ if ... } control directives are not evaluated.
                parts.append(Expr([], inner, line))
            else:
                inner_tokens = [
                    t
                    for t in tokenize(inner, filename)
                    if t.kind not in ("NEWLINE", "EOF")
                ]
                parts.append(Expr(inner_tokens, inner.strip(), line))
            line += src.count("\n", i, end)
            i = end + 1
            continue
        if ch == "\n":
            line += 1
        literal.append(ch)
        i += 1

    raise HCLError("%s:%d: unterminated string" % (filename, start_line))


def _match_brace(src: str, i: int) -> int:
    """Index of the ``}`` closing the ``{`` at ``i``, or -1."""
    depth = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == '"':
            i += 1
            while i < n and src[i] != '"':
                i += 2 if src[i] == "\\" else 1
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def parse(src: str, filename: str = "<string>") -> Body:
    tokens = tokenize(src, filename)
    body, i = _parse_body(tokens, 0, filename, top_level=True)
    if tokens[i].kind != "EOF":
        raise HCLError("%s:%d: unexpected %r" % (filename, tokens[i].line, tokens[i].raw))
    return body


def parse_file(path: str) -> Body:
    with open(path, "r", encoding="utf-8") as handle:
        return parse(handle.read(), path)


def _parse_body(
    tokens: List[Token], i: int, filename: str, top_level: bool = False
) -> Tuple[Body, int]:
    body = Body()
    while True:
        while tokens[i].kind == "NEWLINE":
            i += 1
        token = tokens[i]
        if token.kind == "EOF":
            if not top_level:
                raise HCLError("%s:%d: unexpected end of file, expected '}'" % (filename, token.line))
            return body, i
        if token.is_punct("}"):
            if top_level:
                raise HCLError("%s:%d: unexpected '}'" % (filename, token.line))
            return body, i + 1

        if token.kind != "IDENT":
            raise HCLError(
                "%s:%d: expected an identifier, found %r" % (filename, token.line, token.raw)
            )
        name = token.value
        i += 1

        if tokens[i].is_punct("="):
            i += 1
            expr, i = _read_expr(tokens, i, filename)
            body.attributes[name] = expr
            continue

        labels: List[str] = []
        while True:
            token = tokens[i]
            if token.is_punct("{"):
                i += 1
                break
            if token.kind == "STRING":
                labels.append(token.value if isinstance(token.value, str) else token.raw[1:-1])
                i += 1
                continue
            if token.kind == "IDENT":
                labels.append(token.value)
                i += 1
                continue
            raise HCLError(
                "%s:%d: expected a block label or '{', found %r" % (filename, token.line, token.raw)
            )
        inner, i = _parse_body(tokens, i, filename)
        body.blocks.append(Block(name, labels, inner, token.line))
    # unreachable


_OPEN = {"{": "}", "[": "]", "(": ")"}


def _read_expr(tokens: List[Token], i: int, filename: str) -> Tuple[Expr, int]:
    """Read one attribute value.

    An attribute ends at a newline, at the closing brace of its block, or at the
    next ``ident =`` on the same line -- the single-line form the contract files
    use (``output "x" { backend = "tofu"  value = module.y.z }``).
    """
    start = i
    depth = 0
    collected: List[Token] = []
    while True:
        token = tokens[i]
        if token.kind == "EOF":
            break
        if token.kind == "NEWLINE":
            if depth == 0:
                i += 1
                break
            i += 1
            continue
        if token.kind == "PUNCT":
            if token.value in _OPEN:
                depth += 1
            elif token.value in ("}", "]", ")"):
                if depth == 0:
                    break
                depth -= 1
        if (
            depth == 0
            and collected
            and token.kind == "IDENT"
            and tokens[i + 1].is_punct("=")
        ):
            break
        collected.append(token)
        i += 1

    if not collected:
        raise HCLError("%s:%d: attribute has no value" % (filename, tokens[start].line))
    raw = " ".join(t.raw for t in collected)
    raw = tidy(raw)
    return Expr(collected, raw, collected[0].line), i


def tidy(raw: str) -> str:
    for punct in (".", "[", "]", "(", ")", ","):
        raw = raw.replace(" " + punct, punct)
    for punct in (".", "[", "("):
        raw = raw.replace(punct + " ", punct)
    return raw.strip()


# --------------------------------------------------------------------------
# Evaluation of the literal subset
# --------------------------------------------------------------------------


def evaluate(expr: Optional[Expr], scope: Optional[Dict[str, Any]] = None) -> Any:
    if expr is None:
        return UNRESOLVED
    return _eval_tokens(expr.tokens, scope or {})


def _eval_tokens(tokens: Sequence[Token], scope: Dict[str, Any]) -> Any:
    tokens = _strip_parens(tokens)
    if not tokens:
        return UNRESOLVED

    if len(tokens) == 1:
        token = tokens[0]
        if token.kind == "STRING":
            return _eval_string(token, scope)
        if token.kind == "HEREDOC":
            return token.value
        if token.kind == "NUMBER":
            return token.value
        if token.kind == "IDENT":
            if token.value == "true":
                return True
            if token.value == "false":
                return False
            if token.value == "null":
                return None

    first, last = tokens[0], tokens[-1]
    if first.is_punct("[") and last.is_punct("]"):
        items = []
        for chunk in split_top_level(tokens[1:-1], ","):
            if not chunk:
                continue
            value = _eval_tokens(chunk, scope)
            if value is UNRESOLVED:
                return UNRESOLVED
            items.append(value)
        return items
    if first.is_punct("{") and last.is_punct("}"):
        obj: Dict[str, Any] = {}
        for chunk in split_top_level(tokens[1:-1], ","):
            if not chunk:
                continue
            key_tokens, value_tokens = _split_once(chunk, ("=", ":"))
            if value_tokens is None:
                return UNRESOLVED
            key = _literal_key(key_tokens, scope)
            if key is UNRESOLVED:
                return UNRESOLVED
            value = _eval_tokens(value_tokens, scope)
            if value is UNRESOLVED:
                return UNRESOLVED
            obj[str(key)] = value
        return obj

    path = traversal(tokens)
    if path is not None:
        return _lookup(path, scope)
    return UNRESOLVED


def _strip_parens(tokens: Sequence[Token]) -> Sequence[Token]:
    while (
        len(tokens) >= 2
        and tokens[0].is_punct("(")
        and tokens[-1].is_punct(")")
        and _balanced(tokens[1:-1])
    ):
        tokens = tokens[1:-1]
    return tokens


def _balanced(tokens: Sequence[Token]) -> bool:
    depth = 0
    for token in tokens:
        if token.kind == "PUNCT":
            if token.value in _OPEN:
                depth += 1
            elif token.value in ("}", "]", ")"):
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0


def _eval_string(token: Token, scope: Dict[str, Any]) -> Any:
    out: List[str] = []
    for part in token.parts or []:
        if isinstance(part, str):
            out.append(part)
            continue
        value = _eval_tokens(part.tokens, scope)
        if value is UNRESOLVED or isinstance(value, (list, dict)):
            return UNRESOLVED
        if value is True:
            out.append("true")
        elif value is False:
            out.append("false")
        elif value is None:
            out.append("null")
        else:
            out.append(str(value))
    return "".join(out)


def _literal_key(tokens: Sequence[Token], scope: Dict[str, Any]) -> Any:
    if len(tokens) == 1 and tokens[0].kind == "IDENT":
        return tokens[0].value
    return _eval_tokens(tokens, scope)


def split_top_level(tokens: Sequence[Token], sep: str) -> List[List[Token]]:
    chunks: List[List[Token]] = []
    current: List[Token] = []
    depth = 0
    for token in tokens:
        if token.kind == "PUNCT":
            if token.value in _OPEN:
                depth += 1
            elif token.value in ("}", "]", ")"):
                depth -= 1
            elif token.value == sep and depth == 0:
                chunks.append(current)
                current = []
                continue
        current.append(token)
    chunks.append(current)
    return chunks


def _split_once(
    tokens: Sequence[Token], seps: Tuple[str, ...]
) -> Tuple[List[Token], Optional[List[Token]]]:
    depth = 0
    for index, token in enumerate(tokens):
        if token.kind == "PUNCT":
            if token.value in _OPEN:
                depth += 1
            elif token.value in ("}", "]", ")"):
                depth -= 1
            elif token.value in seps and depth == 0:
                return list(tokens[:index]), list(tokens[index + 1 :])
    return list(tokens), None


def traversal(tokens: Sequence[Token]) -> Optional[List[str]]:
    """``global.platform.cluster_stack_id`` -> ``["global", "platform", ...]``.

    Returns ``None`` for anything that is not a plain dotted traversal, which is
    how function calls, ternaries and arithmetic are rejected.
    """
    tokens = _strip_parens(tokens)
    if not tokens or tokens[0].kind != "IDENT":
        return None
    path = [tokens[0].value]
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token.is_punct("."):
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if nxt is None or nxt.kind not in ("IDENT", "NUMBER"):
                return None
            path.append(str(nxt.value))
            index += 2
            continue
        if token.is_punct("["):
            close = index + 2
            if (
                close < len(tokens)
                and tokens[close].is_punct("]")
                and tokens[index + 1].kind in ("STRING", "NUMBER")
            ):
                value = tokens[index + 1].value
                if value is None:
                    return None
                path.append(str(value))
                index = close + 1
                continue
            return None
        return None
    return path


def _lookup(path: Sequence[str], scope: Dict[str, Any]) -> Any:
    current: Any = scope
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
            continue
        return UNRESOLVED
    if isinstance(current, dict) or isinstance(current, list):
        return current
    return current
