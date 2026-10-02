"""Meter: the one place a time signature is turned into beats and steps."""

DEFAULT_SIGNATURE = (4, 4)


def parse_time_signature(signature: str) -> tuple[int, int]:
    """"6/8" -> (6, 8). Falls back to 4/4 on anything unparseable."""
    try:
        numerator, denominator = signature.split("/")
        return int(numerator), int(denominator)
    except (ValueError, AttributeError):
        return DEFAULT_SIGNATURE


def beats_per_bar(signature: str) -> float:
    """Quarter-note beats in one bar, which is the unit `Note.dur` counts in.

    A 6/8 bar is six eighth notes, so three quarter-note beats.
    """
    numerator, denominator = parse_time_signature(signature)
    return numerator * (4 / denominator)


def steps_per_bar(signature: str, steps_per_beat: int = 4) -> int:
    """Grid steps in one bar: 16 sixteenths in 4/4, 12 in 6/8, 14 in 7/8."""
    return round(beats_per_bar(signature) * steps_per_beat)
