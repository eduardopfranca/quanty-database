"""
Business-day calendar (Mon-Fri).

Minimal weekday logic used by freshness checks to decide whether an
indicator's data is current. B3 holidays are NOT handled yet — when they are,
they get added here and every call site benefits without changing.
"""
from datetime import date, timedelta


def is_business_day(d: date) -> bool:
    """True if `d` is a weekday (Mon-Fri). Holidays are not considered yet."""
    return d.weekday() < 5  # Monday=0 ... Friday=4, Saturday=5, Sunday=6


def last_business_day(reference: date | None = None) -> date:
    """Most recent business day on or before `reference` (default: today).

    A weekday returns itself; a weekend walks back to the previous Friday.
    """
    d = reference if reference is not None else date.today()
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


if __name__ == "__main__":
    today = date.today()
    print(f"Today: {today} ({today:%a}) -> last_business_day: {last_business_day()}\n")

    # Fixed sanity checks (June 2026): 5th=Fri, 6th=Sat, 7th=Sun, 8th=Mon.
    for d in (date(2026, 6, 5), date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)):
        print(f"  last_business_day({d} {d:%a}) -> {last_business_day(d)}")