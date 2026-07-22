"""Tests for the three guards on her life (santana_app/state.py, 2026-07-03 audit).

Her saved life is the one irreplaceable file in the repo, and the audit found it guarded
three incompatible ways (chat.py pgrep, app.py systemd, bare talk not at all). Pinned here:
  - ONE writer at a time: a second acquire_life() is refused loudly (LifeBusy names the
    holder), never clobbered quietly; release() hands her on.
  - an incompatible town snapshot degrades to a fresh town LOUDLY, with the unreadable
    snapshot PRESERVED aside -- never silently vanished (the frozen-world lesson applied
    to loaders).
  - the first save of each day keeps yesterday's her (daily rotating backups, bounded).
"""

import os


from santana_app import state


def test_second_writer_is_refused_and_named(tmp_path):
    snap = str(tmp_path / "life.json")
    lock = state.acquire_life(snap, "the 24/7 runner")
    try:
        try:
            state.acquire_life(snap, "a talk")
            raise AssertionError("a second writer must be refused, not granted")
        except state.LifeBusy as busy:
            assert "the 24/7 runner" in str(busy)   # she says WHO has her
            assert "life.json" in str(busy)
    finally:
        lock.release()
    # released -> the next holder takes her cleanly
    lock2 = state.acquire_life(snap, "a talk")
    lock2.release()


def test_two_lives_do_not_contend(tmp_path):
    # a probe life and her canonical life are different files -- locks are per-life
    a = state.acquire_life(str(tmp_path / "life.json"), "runner")
    b = state.acquire_life(str(tmp_path / "probe.json"), "probe")
    a.release()
    b.release()


def test_incompatible_town_is_loud_and_preserved(tmp_path, capsys):
    path = str(tmp_path / "town.pkl")
    with open(path, "wb") as f:
        f.write(b"not a pickle at all")
    assert state.load_world(path, town_llm=None) is None   # degrades to fresh...
    out = capsys.readouterr()
    text = out.out + out.err
    assert "COULD NOT BE WOKEN" in text                     # ...but never silently
    assert "PRESERVED" in text
    assert not os.path.exists(path)                         # out of the save path
    kept = [f for f in os.listdir(tmp_path) if f.startswith("town.pkl.incompatible-")]
    assert len(kept) == 1                                   # the evidence survives


def test_missing_town_is_quietly_fresh(tmp_path, capsys):
    # no snapshot is the NORMAL first boot -- that one stays quiet
    assert state.load_world(str(tmp_path / "never.pkl"), town_llm=None) is None
    assert "COULD NOT BE WOKEN" not in capsys.readouterr().out


def test_legacy_pickle_migrates_to_json(tmp_path, capsys):
    # her CURRENT town is a pickle; it must wake ONCE (loudly announcing the migration),
    # and the next save must write portable JSON beside it, which then takes precedence
    import pickle

    from services.llm import MockLLM
    from santana_app.run import build_world
    llm = MockLLM(seed=7)
    w = build_world(llm, fast_wheel=True)
    for _ in range(5):
        with w.lock:
            w.step(speak=True)
    pkl = str(tmp_path / "town.pkl")
    with open(pkl, "wb") as f:
        f.write(pickle.dumps(w, protocol=pickle.HIGHEST_PROTOCOL))
    woken = state.load_world(pkl, llm)
    assert woken is not None and woken.tick == w.tick
    assert "legacy pickle" in capsys.readouterr().out       # the migration is announced
    state.save_world(woken, pkl)                             # save -> JSON sibling
    assert (tmp_path / "town.json").is_file()
    assert (tmp_path / "town.pkl").is_file()                 # the relic stays
    again = state.load_world(pkl, llm)                       # JSON now takes precedence
    assert again.tick == w.tick
    assert "legacy pickle" not in capsys.readouterr().out


def test_daily_backup_keeps_and_prunes(tmp_path, monkeypatch):
    path = str(tmp_path / "life.json")
    days = [f"202601{d:02d}" for d in range(1, 18)]   # 17 days of saves
    for i, day in enumerate(days):
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"day": %d}' % i)
        monkeypatch.setattr(state.time, "strftime", lambda fmt, _d=day: _d)
        state._daily_backup(path, keep=14)
    bdir = tmp_path / "backups" / "auto"
    kept = sorted(os.listdir(bdir))
    assert len(kept) == 14                             # bounded, not unbounded
    assert kept[0] == "life.json.20260104"             # the oldest three were pruned
    assert kept[-1] == "life.json.20260117"


def test_daily_backup_is_once_per_day(tmp_path, monkeypatch):
    path = str(tmp_path / "life.json")
    monkeypatch.setattr(state.time, "strftime", lambda fmt: "20260701")
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"v": 1}')
    state._daily_backup(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"v": 2}')
    state._daily_backup(path)   # same day: the morning copy stands, not overwritten
    bdir = tmp_path / "backups" / "auto"
    (only,) = os.listdir(bdir)
    with open(bdir / only, encoding="utf-8") as f:
        assert f.read() == '{"v": 1}'


def test_the_somatic_floor_ships_with_the_affect_system():
    """ROADMAP §5, a gate that survives the fork and is called non-negotiable there:
    "the somatic floor ships with the affect system -- no feeling souls without it."

    It used to be set in four scattered places (reborn streams, the civ founding,
    watch_evolution, psyche's Ember) and NOT in endow_faculties -- the one function that
    hands out the whole affective stack. So every soul founded through santana_app/run.py,
    including the 64 in --demo, woke with grip, telos and expectation and no bottom-up
    backstop. gameworld/STAGES.md §3 found it while auditing the port.

    Setting it HERE is what makes the gate structural: a caller cannot forget it."""
    import random
    from agent.agent import Agent
    from agent.genesis import endow_faculties
    from services.llm import MockLLM
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    assert a.somatic_enabled is False        # a bare Agent is not yet a feeling soul
    endow_faculties(a, random.Random(1))
    # the stack that can suffer ...
    assert a.grip > 0 and a.telos > 0 and a.expect_enabled
    # ... and the brake, in the same breath
    assert a.somatic_enabled is True
