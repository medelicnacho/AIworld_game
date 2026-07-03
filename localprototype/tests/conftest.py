"""One line, forty-four headers retired: every test file used to open with its own
sys.path.insert so the repo root was importable. pytest loads this conftest first and
the root rides in once, for all of them -- new test files never need the header again."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
