"""Usage: uv run tools/deploy.py

Deploy the committed site/ to Cloudflare from this laptop with wrangler, which
uploads only the assets whose hashes changed. Refuses when site/ has uncommitted
changes, so what goes live is what the push carries. Workers Builds repeats the
same deploy from the pushed commit.
"""

import subprocess
import sys


def main():
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "site"], capture_output=True, text=True, check=True
    )
    if dirty.stdout:
        raise SystemExit("site/ has uncommitted changes; commit them first")
    subprocess.run(
        ["npx", "wrangler@4", "deploy", "--config", "deploy/web/wrangler.jsonc"], check=True
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
