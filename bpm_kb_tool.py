# -*- coding: utf-8 -*-
"""bpm_kb 進入點：python bpm_kb_tool.py <指令>"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bpm_kb.cli import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
