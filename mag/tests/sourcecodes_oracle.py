"""Usage: sourcecodes_oracle.py <root> <edition> <destination>"""

import runpy
import sys
from pathlib import Path

root, edition, destination = sys.argv[1:4]
module = runpy.run_path("tools/sourcecodes.py")
module["generate"].__globals__["ROOT"] = Path(root)
module["generate"](edition, Path(destination))
