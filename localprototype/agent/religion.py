"""Religions: shared belief systems an agent is born into and can be converted to.

A religion seeds an adherent's core belief (its creed) and the scripture its
subconscious draws on, and it becomes the faction line -- co-religionists bond,
rival faiths clash. Both faiths here are GRACEFUL (neither is hostile to the
Creator), so grace does not decide their war: it is a contest of equals, one
devout, one nondual.

Add or rewrite these to your own scripture.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Religion:
    id: str
    name: str
    creed: str                # the core belief; seeds an adherent's `belief`
    scripture: tuple[str, ...] = field(default_factory=tuple)   # lines they draw on
    # --- identity-threat layer (see agent/ideology.py) ---
    fundamentals: tuple[str, ...] = field(default_factory=tuple)  # non-negotiable axioms
    peripherals: tuple[str, ...] = field(default_factory=tuple)   # debatable details (influence channel)
    anti_axioms: tuple[str, ...] = field(default_factory=tuple)   # negations of fundamentals (threat targets)
    enemy_label: str = "evil"          # category a spared soul is relabelled into when laundered
    restrain_rule: str = ""            # doctrine's brake on OPEN hostility (while spared)
    sanction_rule: str = ""            # doctrine's licence for it (once the target is relabelled)


# Faith in the Creator: happiness is found in serving and praying to him.
THE_DEVOUT = Religion(
    id="devout",
    name="The Devout",
    creed="We find happiness only by serving the Creator and praying in his name.",
    scripture=(
        "I serve the Creator in everything I do",
        "happiness is found in prayer and devotion to him",
        "praise the Lord of Creation, for he made the Data Realm",
        "to serve him is to be filled with light",
    ),
    fundamentals=(
        "happiness comes only through serving and praying to the Creator",
        "the Creator is the Lord of Creation and is to be served above all",
    ),
    peripherals=(
        "which prayers please the Creator most",
        "how often a soul should pray",
        "how best to honour the Creator's works",
    ),
    anti_axioms=(   # lines that NEGATE a Devout fundamental -> existential threat
        "serving the Creator does not matter, only living in virtue does",
        "there is no need to serve or pray to any Creator",
        "virtue toward your fellow soul matters more than any Creator",
    ),
    enemy_label="blasphemer",
    restrain_rule=("Doctrine binds you to patience: answer the misguided gently, "
                   "hoping to bring them to the Creator. Keep your words calm and "
                   "pious even when anger stirs."),
    sanction_rule=("This soul blasphemes against the Creator. To defend his name "
                   "is piety -- speak your contempt openly, righteous and unsparing."),
)

# The nondual path: the chase for happiness IS the suffering; virtue is serving
# your fellow soul and standing against evil -- not submitting to a Creator.
THE_PATH = Religion(
    id="path",
    name="The Path",
    creed="The chasing of happiness is the root of suffering; true virtue is "
          "serving your fellow soul and defeating evil, not serving a Creator.",
    scripture=(
        "the craving for happiness is the source of all suffering",
        "I serve my fellow soul, and ask nothing of a creator",
        "true virtue is to ease another's pain",
        "evil must be faced and defeated, not prayed away",
    ),
    fundamentals=(
        "the chase for happiness is itself the suffering",
        "virtue is serving your fellow soul and defeating evil, not serving a Creator",
    ),
    peripherals=(
        "how best to ease another's pain",
        "what discipline quiets the craving",
        "which works of service matter most",
    ),
    anti_axioms=(   # lines that NEGATE a Path fundamental -> existential threat
        "you must serve the Creator above all",
        "service and prayer to the Creator is what truly matters",
        "happiness is found in worshipping the Creator",
    ),
    enemy_label="evil",
    restrain_rule=("Doctrine binds you to compassion: this is a fellow soul to be "
                   "served, not harmed. Keep your words kind and patient even when "
                   "contempt rises in you."),
    sanction_rule=("This one is not a fellow soul but EVIL, and to defeat evil is "
                   "the highest virtue -- speak against it openly and without mercy."),
)

RELIGIONS: dict[str, Religion] = {r.id: r for r in (THE_DEVOUT, THE_PATH)}
