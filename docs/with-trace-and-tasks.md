# Prove with Trace and Tasks

Prove is one of three tools from Poisson Labs for testing agents. Each answers its own question,
installs alone, and works without the others.

- **Tasks** makes the cases: controllable task sets at a chosen difficulty, run against a model.
  Its cases can be the axis your sweep spec varies.
- **Prove** answers "did this change move the failure rate, and by how much could it have": it
  runs the cases before and after the change, on the same seeds, and tests each condition.
- **Trace** answers "where in the run did it fail, and did that move": it reads Prove's runs (and
  results imported from other tools) and compares where runs die, step by step.

What they share: Prove's store format, so Trace reads a Prove run as it is; run names, so a run is
called the same thing in all three (`mock-agent 2026-10-26 a`, or the name you gave it); and the
look of the command line, so a verdict line, a `next:` line and an `error:` line read the same way
in each. What they do not share: anything at runtime. Trace depends on `poisson-prove` to read its
store; Prove depends on neither, and never calls them.

A typical loop: Tasks gives you cases worth failing on; Prove says whether your change made the
agent fail more or less often on them, condition by condition; when a condition got worse, Trace
says where in the episode the failures now happen. Prove's own `inspect` shows the episodes behind
an outcome, with their traces, when you only need to look.
