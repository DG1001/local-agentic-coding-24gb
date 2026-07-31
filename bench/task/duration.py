"""ISO-8601 duration parsing.

Converts duration strings like "P1DT2H30M" into a number of seconds.

Conventions used by this module (fixed, do not change):
  1 minute = 60 s
  1 hour   = 3600 s
  1 day    = 86400 s
  1 week   = 7 days
  1 month  = 30 days   (nominal)
  1 year   = 365 days  (nominal)

Grammar:
  [-]P[nY][nM][nW][nD][T[nH][nM][nS]]

The 'M' designator means MONTHS before the 'T' separator and MINUTES after it.
Numbers may be fractional (e.g. "PT1.5S"). A leading '-' negates the whole
duration.
"""

import re

_PATTERN = re.compile(
    r"^(?P<sign>-)?P"
    r"(?:(?P<years>[\d.]+)Y)?"
    r"(?:(?P<months>[\d.]+)M)?"
    r"(?:(?P<days>[\d.]+)D)?"
    r"(?:T"
    r"(?:(?P<hours>[\d.]+)H)?"
    r"(?:(?P<minutes>[\d.]+)M)?"
    r"(?:(?P<seconds>[\d.]+)S)?"
    r")?$"
)

_UNITS = {
    "years": 365 * 86400,
    "months": 30 * 86400,
    "days": 86400,
    "hours": 3600,
    "minutes": 60,
    "seconds": 1,
}


def parse_duration(text):
    """Parse an ISO-8601 duration string and return the number of seconds.

    Returns a float. Raises ValueError on malformed input.
    """
    if not isinstance(text, str) or not text:
        raise ValueError("duration must be a non-empty string")

    match = _PATTERN.match(text.strip())
    if match is None:
        raise ValueError("malformed duration: %r" % (text,))

    parts = match.groupdict()

    total = 0
    for name, factor in _UNITS.items():
        raw = parts.get(name)
        if raw is None:
            continue
        total += int(raw) * factor

    return total


def format_duration(seconds):
    """Render a number of seconds back into an ISO-8601 duration string."""
    if seconds < 0:
        return "-" + format_duration(-seconds)

    remaining = seconds
    out = ["P"]
    days, remaining = divmod(remaining, 86400)
    if days:
        out.append("%dD" % days)
    hours, remaining = divmod(remaining, 3600)
    minutes, remaining = divmod(remaining, 60)
    if hours or minutes or remaining:
        out.append("T")
        if hours:
            out.append("%dH" % hours)
        if minutes:
            out.append("%dM" % minutes)
        if remaining:
            out.append("%gS" % remaining)
    if len(out) == 1:
        return "PT0S"
    return "".join(out)
