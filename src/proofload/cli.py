import argparse

from proofload import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="proofload")
    parser.add_argument("--version", action="version", version=__version__)
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 1
    return 0
