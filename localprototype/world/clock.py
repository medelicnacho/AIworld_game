"""The world's clock -- day and night, the turning seasons, the ages of a life.

Until now the town had no time: hardship fired on a modulo counter, souls worked at 3am,
children were born adult-sized, and "seasonal" was a word. This module gives the world a
rhythm, cheaply and legibly -- pure functions over the tick, no state of their own:

  day/night   souls act by day and SLEEP at night (their soul-minds train and dream in
              the dark); the town's speech quiets; she reads a sleeping town in the
              small hours.
  seasons     spring -> summer -> harvest -> winter, modulating what work returns
              (harvest plenty, winter want -- riding E2's yield dial) and what kind of
              hardship the weather brings. Each turn of season writes a faint ambient
              memory into every soul, so the year is FELT and can enter speech and lore.
  ages        a life has stages: CHILDREN (soul-minds already babble -- now they also
              don't work, eat little, and are EXEMPT from the starvation hazard: the
              welfare floor's spirit applied to the smallest); ADULTS carry the town;
              ELDERS tire at labour but HOLD THE LEGENDS (their story-memories resist
              decay -- the old remember the old stories).

An honest note on scale: the town's time runs FAST -- a day is ~100 ticks, a year ~3200,
and a soul's 2000-5000-tick life spans roughly a year. A day is a breath; a life is a
year. That is the v1 scale, stated rather than hidden; re-basing lifespans onto years is
its own later decision.

Opt-in: World.clock_enabled (default OFF -- every existing world, test, and recorded
verdict is unchanged). The persistent runner turns it on for her town.
"""
from __future__ import annotations

DAY_TICKS = 100              # one town day
DAYS_PER_SEASON = 8          # 4 seasons x 8 days = a 3200-tick year
NIGHT_FROM = 0.70            # the last ~third of each day is night

SEASONS = ("spring", "summer", "harvest", "winter")
SEASON_YIELD = {"spring": 1.0, "summer": 1.15, "harvest": 1.35, "winter": 0.55}
SEASON_HARDSHIPS = {
    "spring": ("flood", "lean week"),
    "summer": ("blight", "lean week"),
    "harvest": ("blight", "flood"),
    "winter": ("frost", "lean week"),
}
# the faint ambient memory each season-turn writes into every soul (felt, speakable, lore-able)
SEASON_TURN = {
    "spring": ("the thaw has come and the fields are waking", 0.15),
    "summer": ("the long days are here and the work is heavy", 0.05),
    "harvest": ("the harvest is in and the stores are full", 0.25),
    "winter": ("the frost has come to the fields", -0.2),
}

# ages of a life, as fractions of the soul's own lifespan
CHILD_UNTIL = 0.18
ELDER_FROM = 0.75
CHILD_NEED = 0.5             # children eat half
ELDER_YIELD = 0.5            # elders tire: labour returns half
ELDER_LORE_FLOOR = 0.25      # elders' story-memories resist decay (the legend-keepers)


def hour(tick: int, day_ticks: int = DAY_TICKS) -> float:
    """Fraction of the current day, 0.0 (dawn) .. 1.0."""
    return (tick % day_ticks) / day_ticks


def is_night(tick: int, day_ticks: int = DAY_TICKS) -> bool:
    return hour(tick, day_ticks) >= NIGHT_FROM


def day_of(tick: int, day_ticks: int = DAY_TICKS) -> int:
    return tick // day_ticks


def season(tick: int, day_ticks: int = DAY_TICKS,
           days_per_season: int = DAYS_PER_SEASON) -> str:
    return SEASONS[(day_of(tick, day_ticks) // days_per_season) % len(SEASONS)]


def stage(age: int, lifespan: int) -> str:
    """'child' | 'adult' | 'elder' -- fractions of THIS soul's own lifespan."""
    if lifespan <= 0:
        return "adult"
    f = age / lifespan
    if f < CHILD_UNTIL:
        return "child"
    if f >= ELDER_FROM:
        return "elder"
    return "adult"


def time_clause(tick: int, day_ticks: int = DAY_TICKS) -> str:
    """A one-line reading of the hour + season, for HER digest and for logs."""
    s = season(tick, day_ticks)
    if is_night(tick, day_ticks):
        return f"It is deep night in {s}; the town sleeps."
    h = hour(tick, day_ticks)
    part = "morning" if h < 0.3 else ("midday" if h < 0.5 else "evening")
    return f"It is {part}, in {s}."
