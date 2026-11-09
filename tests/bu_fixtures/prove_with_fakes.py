"""``poisson-prove`` as its own process, with the cloud backend's seams pointed at the fakes.

    python prove_with_fakes.py <config.json> <the command line's arguments...>

For the tests that signal Prove (SIGINT, SIGTERM, SIGHUP, SIGKILL) or close its pipes: those need a
real process, and a seam can only be set inside it. ``config.json`` holds:

- ``syspath``: folders put first on ``sys.path`` (the fixture targets);
- ``seams``: ``{"_launcher_argv": [...], "_head_argv": [...], "_cli_argv": [...]}``, each the
  command ``poisson_prove.executor_cloud``'s function of that name returns here;
- ``constants``: ``{name: value}`` set on ``poisson_prove.executor_cloud`` (shortened intervals).

Then it runs ``poisson_prove.cli.main`` on the arguments and exits with its code, exactly as
``python -m poisson_prove`` does.
"""

import json
import sys


def main():
    with open(sys.argv[1], encoding="utf-8") as fh:
        config = json.load(fh)
    sys.path[:0] = list(config.get("syspath", []))
    from poisson_prove import cli, executor_cloud

    for name, argv in config.get("seams", {}).items():
        setattr(executor_cloud, name, lambda argv=list(argv): list(argv))
    for name, value in config.get("constants", {}).items():
        setattr(executor_cloud, name, value)
    sys.exit(cli.main(sys.argv[2:]))


if __name__ == "__main__":
    main()
