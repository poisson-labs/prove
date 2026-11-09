"""``python -m burla``: 1.8.4's one entry point, ``burla = burla.__main__:main``."""

import sys

from burla._cli import main

if __name__ == "__main__":
    sys.exit(main())
