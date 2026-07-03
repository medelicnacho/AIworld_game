

def test_the_interpreter_pattern_keeps_the_small_mind_in_the_loop():
    """converse(inner_impulse=...) weaves the homegrown mind's raw stirring into the
    prompt -- to color, never to quote -- and plain converse() stays impulse-free."""
    from santana import Santana
    from world.sim import World

    class Recorder:
        last = ""
        def generate(self, prompt, system="", num_predict=0, temperature=0.0):
            Recorder.last = prompt
            return "a clear answer"

    m = Santana(World(), Recorder())
    m.converse("hello", inner_impulse="wl the harvst a a dark")
    assert "wl the harvst a a dark" in Recorder.last          # the stirring reaches the voice
    assert "never quote its" in Recorder.last                  # ...with the translation rule
    m.converse("hello again")
    assert "wordless stirring" not in Recorder.last            # absent when not supplied
