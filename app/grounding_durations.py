"""Check explicit numerical durations against approved quotes, not retrieved context."""

from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import re


_SMALL_NUMBERS = dict(zip(
    ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
     "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
     "seventeen", "eighteen", "nineteen"),
    range(20),
))
_TENS = dict(zip(
    ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"),
    range(20, 100, 10),
))
_DASHES = re.escape("-\u2010\u2011\u2012\u2013\u2014\u2015")
_WORD_NUMBER = (
    rf"(?:{'|'.join(_TENS)})(?:[\s{_DASHES}]+(?:{'|'.join(list(_SMALL_NUMBERS)[1:10])}))?"
    rf"|(?:{'|'.join(_SMALL_NUMBERS)})"
)
_DIGITS = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
_NUMERIC = rf"[+\-\u2212]?(?:{_DIGITS}/{_DIGITS}|{_DIGITS}(?:\.\d+)?|\.\d+)"
_NUMBER = rf"(?:{_NUMERIC}|{_WORD_NUMBER})"
_DURATION = re.compile(
    rf"(?<![\w.])(?<!\d[,/])(?<![+\-\u2212])(?P<start>{_NUMBER})"
    rf"(?:\s*(?:[{_DASHES}]|to)\s*(?P<end>{_NUMBER}))?"
    rf"\s*[{_DASHES}]?\s*(?P<unit>seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)
_FIXED_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800}
type Duration = tuple[str, Fraction, Fraction]


def _number(value: str) -> Fraction:
    if value[0].isdigit() or value[0] in "+-\u2212.":
        return Fraction(value.replace(",", "").replace("\u2212", "-"))
    words = re.split(rf"[\s{_DASHES}]+", value.casefold())
    return Fraction(sum((_SMALL_NUMBERS | _TENS)[word] for word in words))


def _durations(text: str, *, reject_invalid: bool = False) -> dict[Duration, str]:
    durations: dict[Duration, str] = {}
    for match in _DURATION.finditer(text):
        # Do not misread the tail of an unsupported compound such as
        # "one hundred and three days" or "one point five days" as a smaller value.
        if re.search(r"\b(?:hundred|thousand|million|billion|point)(?:\s+and)?\s*$",
                     text[:match.start()], re.IGNORECASE):
            continue
        try:
            start = _number(match["start"])
            end = _number(match["end"]) if match["end"] is not None else start
        except ZeroDivisionError:
            if reject_invalid:
                raise ValueError("claimed duration has a zero denominator") from None
            continue
        unit = match["unit"].casefold().rstrip("s")
        if unit in _FIXED_SECONDS:
            start *= _FIXED_SECONDS[unit]
            end *= _FIXED_SECONDS[unit]
            unit = "second"
        # Calendar months/years do not have a fixed duration in seconds.
        durations[(unit, start, end)] = match.group()
    return durations


def validate_duration_evidence(claim_text: str, evidence_quotes: list[str]) -> None:
    """Reject recognized claim durations missing from the selected evidence.

    This checks number-before-unit forms and exact ranges, including cardinal
    words through ninety-nine. It is a consistency gate, not semantic entailment
    or complete extraction of every possible temporal expression.
    """
    supported = {duration for quote in evidence_quotes for duration in _durations(quote)}
    missing = [label for duration, label in _durations(claim_text, reject_invalid=True).items()
               if duration not in supported]
    if missing:
        raise ValueError(
            f"approved evidence does not contain claimed duration(s): {', '.join(missing)}. "
            "Cite and approve an exact excerpt establishing the duration as well as the result."
        )


def duration_fingerprint() -> str:
    """Bind evaluation resumes to this deterministic guard's implementation."""
    return sha256(Path(__file__).read_bytes()).hexdigest()
