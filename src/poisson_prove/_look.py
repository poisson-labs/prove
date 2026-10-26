"""The look of the command line: how numbers, values and glyphs read on a screen.

The library's renderers (``diff``'s markdown, ``report``'s markdown, receipt and heatmap) keep
the number forms they have always had, so their output is the same byte for byte whoever
calls them. The command line asks for the look's forms instead, by rendering inside
:func:`rule10`: rates, shares, deltas and detection limits as fractions to three decimals;
p-values to three decimals or in ``2.3e-08`` form below 0.001; counts with thousands
separators; dollars as ``$1.00``, two significant digits below $0.10; durations as
``1 min 40 s``; a hash at 12 hex characters in text. A renderer reads :func:`active` and
nothing else changes shape.

Everything here is standard library. Nothing here computes a statistic: every function takes
a number it was given and spells it.
"""

from __future__ import annotations

import ast
import json
import math
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

__all__: list[str] = []

_MODE: ContextVar[str] = ContextVar("poisson_prove_look", default="library")


def active() -> bool:
    """Whether the look's number forms are wanted: true inside :func:`rule10`."""
    return _MODE.get() == "rule10"


@contextmanager
def rule10() -> Iterator[None]:
    """Render under the look's forms."""
    token = _MODE.set("rule10")
    try:
        yield
    finally:
        _MODE.reset(token)


@contextmanager
def library() -> Iterator[None]:
    """Render under the library's own forms, whatever the caller is inside."""
    token = _MODE.set("library")
    try:
        yield
    finally:
        _MODE.reset(token)


# ---------- the formats ----------


def no_negative_zero(text: str) -> str:
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text


def fmt_count(value: Any) -> str:
    """A count with thousands separators."""
    return f"{int(value):,}"


def fmt_rate(value: Any) -> str:
    """A rate, share, delta or detection limit: a fraction to three decimals."""
    x = float(value)
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return no_negative_zero(f"{x:.3f}")


def fmt_p(value: Any) -> str:
    """A p-value, q or level: three decimals, or ``2.3e-08`` below 0.001."""
    x = float(value)
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    if x == 0 or abs(x) >= 0.001:
        return no_negative_zero(f"{x:.3f}")
    return f"{x:.1e}"


def fmt_dollars(value: Any) -> str:
    """``$1.00``; two significant digits below $0.10; ``$0`` for nothing at all."""
    x = float(value)
    if x == 0:
        return "$0"
    if x >= 0.1:
        return f"${x:,.2f}"
    d = Decimal(repr(x))
    quantum = Decimal(1).scaleb(d.adjusted() - 1)
    q = d.quantize(quantum, rounding=ROUND_HALF_EVEN)
    return f"${float(q):,.2f}" if q >= Decimal("0.1") else f"${q:f}"


def fmt_duration(seconds: Any) -> str:
    """``3.9 s``, ``1 min 40 s``, ``1 h 36 min``."""
    s = float(seconds)
    if round(s, 1) < 60:
        return f"{s:.1f} s"
    minutes, rest = divmod(int(round(s)), 60)
    if minutes < 60:
        return f"{minutes} min {rest} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min"


def fmt_signed(value: Any) -> str:
    """A change with its sign, ``+0.309`` or ``-0.250``, a zero unsigned; ``none`` for none."""
    if value is None:
        return "none"
    x = float(value)
    if math.isnan(x):
        return "nan"
    text = fmt_rate(abs(x))
    return f"+{text}" if x > 0 else f"-{text}" if x < 0 else text


def condition_words(config: Mapping[str, Any]) -> str:
    """A condition as its axis values, ``gain 0.5 · load 10``, each number as rule 10 prints it."""
    parts = []
    for key, value in config.items():
        number = isinstance(value, (int, float)) and not isinstance(value, bool)
        parts.append(f"{key} {fmt_num(value) if number else value}")
    return " · ".join(parts)


_UTC = re.compile(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d)(:\d\d)(?:\.\d+)?Z$")


def fmt_time(value: Any, *, minute: bool = False) -> str:
    """A UTC time as text, ``2026-10-23T22:36:28Z``, or to the minute, ``2026-10-23 22:36Z``; a
    value that is not a UTC time, as it is."""
    m = _UTC.match(str(value))
    if m is None:
        return str(value)
    return f"{m.group(1)} {m.group(2)}Z" if minute else f"{m.group(1)}T{m.group(2)}{m.group(3)}Z"


def fmt_clock(value: Any) -> str:
    """A UTC time's clock alone, ``22:36:28Z``; a value that is not a UTC time, as it is."""
    m = _UTC.match(str(value))
    return f"{m.group(2)}{m.group(3)}Z" if m else str(value)


def fmt_hash(value: Any) -> str:
    """A hash at 12 hex characters in text."""
    text = str(value)
    return text[:12] if re.fullmatch(r"[0-9a-f]{16,}", text) else text


def fmt_num(value: Any) -> str:
    """A plain number that is none of the above: an integer as a count, a float with at most
    three decimals."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return fmt_count(value)
    x = float(value)
    if math.isnan(x) or math.isinf(x):
        return str(x)
    if x.is_integer() and abs(x) < 1e15:
        return fmt_count(int(x))
    text = f"{x:.10g}"
    if "e" in text or "E" in text:
        return fmt_p(x)
    whole, _, frac = text.partition(".")
    if len(frac) > 3:
        text = f"{x:.3f}"
    return no_negative_zero(text)


def ceil3(value: Any) -> str:
    """A value rounded **up** at three decimals, for an override the reader will paste back."""
    x = float(value)
    up = math.ceil(x * 1000 - 1e-9) / 1000
    if up < x:
        up += 0.001
    return f"{up:.3f}"


# ---------- prose the library wrote, respelled ----------


_RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{4}")
_DATE = re.compile(r"\d{4}-\d{2}(?:-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?Z?)?)?")
_VERSION = re.compile(r"\d+\.\d+\.\d+(?:[.\w-]*)")
_HEX = re.compile(r"[0-9a-f]*[a-f][0-9a-f]*")
_DOLLARS = re.compile(r"\$(\d[\d,]*(?:\.\d+)?)")
_POINTS = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s?(?:pp|points?)\b")
_OVERRIDE = re.compile(r"(--max(?:-group)?-mde)\s+(\d+(?:\.\d+)?)")
_SCI = re.compile(r"(?<![\w.])(\d(?:\.\d+)?)[eE]([+-]?\d+)(?![\w.])")
_FLOAT = re.compile(r"(?<![\w.$])(-?\d+\.\d+)(?![\w.]|%)")
_PERCENT = re.compile(r"(?<![\w.])(-?\d+\.\d+)%")
_INT = re.compile(r"(?<![\w,-])(?<!\d\.)(\d{4,})(?![\w]|\.\d|,\d)")
_SEED = re.compile(r"(?i)(seed|salt)(s?)([\"':= ]*)(\d{4,})\b")


def _respell(text: str) -> str:
    text = _OVERRIDE.sub(lambda m: f"{m.group(1)} {ceil3(m.group(2))}", text)
    text = _DOLLARS.sub(lambda m: fmt_dollars(float(m.group(1).replace(",", ""))), text)
    text = _POINTS.sub(lambda m: fmt_rate(float(m.group(1)) / 100), text)
    text = _PERCENT.sub(lambda m: f"{float(m.group(1)):.1f}%", text)
    text = _SCI.sub(lambda m: fmt_p(float(f"{m.group(1)}e{m.group(2)}")), text)

    def decimals(m: re.Match[str]) -> str:
        whole, _, frac = m.group(1).partition(".")
        if len(frac) <= 3:
            return m.group(1)
        x = float(m.group(1))
        return fmt_p(x) if 0 < abs(x) < 0.001 else fmt_rate(x)

    text = _FLOAT.sub(decimals, text)
    kept: dict[str, str] = {}

    def keep(m: re.Match[str]) -> str:
        key = f"\x00{len(kept)}\x00"
        kept[key] = m.group(0)
        return key

    text = _SEED.sub(keep, text)
    text = _INT.sub(lambda m: fmt_count(int(m.group(1))), text)
    for key, value in kept.items():
        text = text.replace(key, value)
    return text


def reprint(text: str) -> str:
    """``text`` with every number spelled the look's way, leaving alone what is not a number
    to it: run ids, dates and times, versions, hex, seeds and salts, and anything inside double
    quotes (a value the user typed is given back as typed)."""
    protected: dict[str, str] = {}

    def keep(m: re.Match[str]) -> str:
        key = f"\x01{len(protected)}\x01"
        protected[key] = m.group(0)
        return key

    text = re.sub(r'"[^"\n]*"', keep, text)
    text = re.sub(r"\S*/\S*", keep, text)
    # A value given back to the user ("got 1.23456") is given back as typed.
    text = re.sub(r"\bgot \S+", keep, text)
    for pattern in (_RUN_ID, _DATE, _VERSION):
        text = pattern.sub(keep, text)
    text = re.sub(r"(?<![\w.])" + _HEX.pattern + r"(?![\w.])", keep, text)
    text = _respell(text)
    # Later keys can hold earlier ones (a quoted value after ``got``): restore newest first.
    for key, value in reversed(list(protected.items())):
        text = text.replace(key, value)
    return text


# ---------- plain words in a message ----------


_QUOTED = re.compile(r"(?<![A-Za-z0-9])'((?:[^'\\]|\\.)*)'(?![A-Za-z0-9])")
_OBJECT = re.compile(r"<([\w.]+) object at 0x[0-9a-fA-F]+>")
_PATHOBJ = re.compile(r"\b(?:Posix|Windows)?Path\('([^']*)'\)")


def _plain_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return ", ".join(f"{k}={_plain_value(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return ", ".join(_plain_value(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "none"
    return str(value)


def _literal_spans(text: str) -> list[tuple[int, int, str]]:
    """Every bracketed or braced segment of ``text`` that is a Python literal of a list, tuple
    or dict, as ``(start, end, replacement)``."""
    spans: list[tuple[int, int, str]] = []
    i = 0
    while i < len(text):
        if text[i] not in "[{(":
            i += 1
            continue
        close = {"[": "]", "{": "}", "(": ")"}[text[i]]
        depth = 0
        end = -1
        for j in range(i, len(text)):
            if text[j] in "[{(":
                depth += 1
            elif text[j] in "]})":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end < 0:
            i += 1
            continue
        segment = text[i : end + 1]
        if segment[-1] == close and ("'" in segment or '"' in segment or ", " in segment):
            try:
                value = ast.literal_eval(segment)
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                value = None
            if isinstance(value, (list, dict)):
                spans.append((i, end + 1, _plain_value(value)))
                i = end + 1
                continue
        i += 1
    return spans


def plain_words(message: str) -> str:
    """``message`` without Python's spellings: a list or dict printed as itself becomes its
    items, a quoted value takes double quotes, an object's address is its type's name."""
    text = str(message)
    for start, end, replacement in reversed(_literal_spans(text)):
        text = text[:start] + replacement + text[end:]
    text = _PATHOBJ.sub(lambda m: m.group(1), text)
    text = _OBJECT.sub(lambda m: m.group(1).rsplit(".", 1)[-1], text)
    text = _QUOTED.sub(lambda m: f'"{m.group(1)}"', text)
    return text


def one_line(message: str) -> str:
    """A message as one line: its lines joined with ``; `` and runs of blanks collapsed."""
    parts = [part.strip() for part in str(message).splitlines() if part.strip()]
    return "; ".join(parts)


# ---------- glyphs ----------


_ASCII = str.maketrans({"·": "|", "→": "->", "×": "x", "–": "-", "—": "-", "…": "...", "±": "+/-"})
_GLYPHS = "·→×–…±"


def can_encode(encoding: str | None) -> bool:
    """Whether a stream of ``encoding`` can carry the glyphs plain output uses."""
    if not encoding:
        return True
    try:
        _GLYPHS.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def ascii_only(text: str) -> str:
    return text.translate(_ASCII)


# ---------- strict JSON ----------


def strict(value: Any) -> Any:
    """``value`` with every non-finite number replaced by ``null`` and, beside it in its
    object, a ``<key>_note`` saying what the number was."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, float) and not math.isfinite(item):
                out[str(key)] = None
                out[f"{key}_note"] = f"{key} is not a finite number ({item}); given as null"
            else:
                out[str(key)] = strict(item)
        return out
    if isinstance(value, (list, tuple)):
        return [None if isinstance(v, float) and not math.isfinite(v) else strict(v) for v in value]
    return value


def dumps(value: Any) -> str:
    return json.dumps(strict(value), indent=2, allow_nan=False, ensure_ascii=False)


# ---------- commands to copy ----------

#: The characters a shell reads as themselves in a word.
_PLAIN = re.compile(r"[A-Za-z0-9_./:@%+=,#-]+")


def word(text: str) -> str:
    """``text`` as one word a POSIX shell reads back exactly: bare when every character is read
    as itself, else in double quotes with the four characters a shell reads inside them (``"``,
    ``\\``, ``$`` and the backquote) escaped, so no value on the screen is single-quoted or reads
    as a Python repr. A ``!``, which an interactive shell may expand even inside double quotes,
    is written outside them, escaped."""
    if _PLAIN.fullmatch(text):
        return text
    parts = []
    for i, piece in enumerate(text.split("!")):
        if i:
            parts.append("\\!")
        if piece:
            parts.append('"' + re.sub(r'(["\\$`])', r"\\\1", piece) + '"')
    return "".join(parts) or '""'


def command(*words: str) -> str:
    """A command line to copy, each word quoted by :func:`word` where it needs it."""
    return " ".join(word(w) for w in words)


# ---------- the shared words for levels, powers and table cells ----------


def level_label(level: float) -> str:
    """A level as a percentage to at most three decimals, the percent sign after it: ``0.99722``
    as "99.722" and the sign. The one function every label of a level comes from."""
    if math.isnan(level):
        raise ValueError("a level must be a number")
    text = f"{float(level) * 100.0:.3f}".rstrip("0").rstrip(".")
    return f"{text}%"


def times_in(power: float) -> str:
    """A power in words, ``0.8`` as "4 times in 5": the simplest fraction within a twentieth."""
    from fractions import Fraction

    fraction = Fraction(power).limit_denominator(20)
    return f"{fraction.numerator} times in {fraction.denominator}"


def native(value: Any) -> Any:
    """``value`` with numpy scalars as Python numbers and mappings and sequences as dicts and
    lists, all the way down: what a JSON document can hold."""
    item = getattr(value, "item", None)
    if item is not None and type(value).__module__ == "numpy":
        return item()
    if isinstance(value, Mapping):
        return {str(k): native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [native(v) for v in value]
    return value
