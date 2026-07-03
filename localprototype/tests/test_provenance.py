"""Tests for the provenance pass (C2 confidence + C14 source tags + S2 ownership).

One pass over one store, three findings (SELF.md §6.1): every memory always carried
provenance no self ever read. source_tag() is the discriminator that reads it AT RECALL,
through the drift -- so it can honestly err, and its errors (a story worn until it reads
as lived life) are the auditable false memories C14's falsifier measures. mineness (S2)
is ownership as a SEPARABLE field: unowned recall keeps its accuracy and its charge but
declines the autobiography. Pinned here: the discriminator's verdicts, the confusion
pathway (mutations + cross-source merges), the voice gate, and the S2 dissociation
(mood() keeps what recall_self() cannot claim).
"""


from agent.memory import (Memory, MemoryStore, attributed, attribution_strength, hedged,
                          source_tag)


def _mem(**kw):
    base = dict(text="the rain came early", salience=0.6, created_tick=0,
                last_touched_tick=0)
    base.update(kw)
    return Memory(**base)


def test_fresh_memories_tag_by_true_source():
    assert source_tag(_mem(source="self")) == "mine"
    assert source_tag(_mem(source="reflection")) == "mine"
    assert source_tag(_mem(source="heard")) == "witnessed"
    assert source_tag(_mem(source="user")) == "witnessed"
    assert source_tag(_mem(source="event")) == "witnessed"
    assert source_tag(_mem(source="dream")) == "dream"
    assert source_tag(_mem(source="lore", lore_id="ev:1")) == "story"
    assert source_tag(_mem(source="heard", lore_id="ev:1")) == "story"   # a retelling received
    assert source_tag(_mem(source="doctrine")) == "doctrine"


def test_drift_wears_the_frame_to_unsure_then_to_believed_mine():
    # a STORY: pure word-drift wears the frame only SLOWLY (content doubt is C2's axis,
    # not this one) -- but cross-source merges smear it fast
    story = _mem(source="lore", lore_id="ev:7")
    assert source_tag(story) == "story"
    story.mutation_count = 3                       # worn words, frame intact: still a story
    assert source_tag(story) == "story"
    story.mutation_count = 2
    story.alien_merges = 1                         # retold in my own voice, once
    assert source_tag(story) == "unsure"           # the honest middle
    story.mutation_count = 3
    story.alien_merges = 2                         # ...twice more, words still wearing
    assert source_tag(story) == "mine"             # the confident false memory
    # ...while the experimenter's ground truth NEVER decays:
    assert story.lore_id == "ev:7"                 # the lie is auditable end-to-end
    assert attribution_strength(story) < 0.3
    # and a WITNESSED event worn by pure drift keeps its life -- it doubts its words
    # (C2's hedge) without disclaiming having lived it (the v1 conflation, fixed)
    assert source_tag(_mem(source="event", mutation_count=4)) == "witnessed"


def test_doctrine_never_loses_its_frame():
    d = _mem(source="doctrine", mutation_count=9, alien_merges=5)
    assert source_tag(d) == "doctrine"


def test_cross_source_merge_is_counted():
    s = MemoryStore(seed=1)
    s.write("the fire took the mill by the river", tick=1, source="heard")
    # near-identical telling arrives from a DIFFERENT source -> merges, frame smears
    s.write("the fire took the mill by the river bank", tick=2, source="self")
    (m,) = s.items
    assert m.alien_merges == 1
    assert m.source == "heard"                     # resident frame kept, blend recorded
    # same-source reinforcement does NOT smear
    s.write("the fire took the mill by the river", tick=3, source="heard")
    assert m.alien_merges == 1


def test_attributed_voice_gate():
    assert "(I dreamt it, I think)" in attributed(_mem(source="dream"))
    assert "(a story I was told)" in attributed(_mem(source="lore", lore_id="ev:1"))
    assert "(I no longer know if I lived this" in attributed(
        _mem(source="lore", lore_id="ev:1", mutation_count=2, alien_merges=1))
    # a fully-worn story presents as OWN memory -- gate falls through to the C2 hedge,
    # which still voices the wear (the frame lied; the drift doubt did not)
    worn = _mem(source="lore", lore_id="ev:1", mutation_count=3, alien_merges=2)
    assert attributed(worn) == hedged(worn)
    # clean lived memory: no annotation at all
    assert attributed(_mem(source="self")) == "the rain came early"


def test_s2_unowned_declines_the_autobiography():
    un = _mem(source="self", mineness=0.0)
    assert "though not, I think, to me" in attributed(un)
    # ownership is SEPARABLE: content, accuracy, provenance untouched
    assert un.text == "the rain came early"
    assert source_tag(un) == "mine"                # the discriminator is a different axis


def test_s2_dissociation_mood_keeps_what_the_story_cannot_claim():
    s = MemoryStore(seed=2)
    s.write("I keep the north field", tick=1, source="self")
    wound = s.write("the flood took what I had", tick=2, source="self",
                    emotion=-0.9, mineness=0.0)    # an UNOWNED wound
    # the wound still bends the lived mood (behaviour)...
    assert s.mood() < 0.0
    # ...but vanishes from the identity's raw material (report)
    told = s.recall_self(k=5)
    assert all(m is not wound for m in told)
    assert any("north field" in m.text for m in told)
    # and recall() itself is UNCHANGED by ownership -- accuracy intact (the ablation
    # falsifier's substrate half: mineness must not touch the ranking)
    assert wound in s.recall(k=5)


def test_old_snapshots_wake_cleanly_without_the_new_fields():
    # THE RULE (state.py): every post-snapshot field gets a default. A Memory restored
    # from a pre-provenance pickle lacks the attrs entirely -- the readers must getattr.
    m = _mem(source="lore", lore_id="ev:2")
    del m.__dict__["alien_merges"]
    del m.__dict__["mineness"]
    assert source_tag(m) == "story"
    assert attributed(m) == m.text + " (a story I was told)"
    assert attribution_strength(m) == 1.0
