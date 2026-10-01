# SPDX-License-Identifier: AGPL-3.0-only
"""
Entry point for python -m arca
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
