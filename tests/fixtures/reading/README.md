# What the reading tests read

`diff-quickstart.json` is what `poisson-prove --store prove-runs diff A B --json` printed for the
quickstart pair of `../stores-0.0.1/store`, before `diff`'s default output changed. The change was not
to move the JSON, and `tests/test_diff_plain_words.py` holds it to this file, its floats to six places.
