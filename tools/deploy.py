"""Usage: uv run tools/deploy.py [commit]

Confirm that Cloudflare Workers Builds deployed the pushed commit (default:
HEAD). Waits for its build to finish; when no build appears for the commit
within three minutes (a dropped GitHub push event), deploys site/ from this
laptop with wrangler instead. Exits non-zero when the build fails.
"""

import json
import subprocess
import sys
import time

SCRIPT = "berreta-futura-web"
APPEAR = 180
FINISH = 1200


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def script_tag():
    found = json.loads(run("cf", "workers", "scripts", "search", "--name", SCRIPT))
    return found[0]["id"]


def build_for(tag, commit):
    listed = json.loads(run("cf", "builds", "list", "--external-script-id", tag))
    builds = listed if isinstance(listed, list) else listed.get("result", [])
    for build in builds:
        meta = build.get("build_trigger_metadata") or {}
        if meta.get("commit_hash", "").startswith(commit):
            return build
    return None


def wait(tag, commit):
    start = time.time()
    while time.time() - start < FINISH:
        build = build_for(tag, commit)
        if build is None and time.time() - start > APPEAR:
            return None
        if build and build["status"] == "stopped":
            return build["build_outcome"]
        time.sleep(15)
    return "timeout"


def main():
    if sys.argv[1:2] in (["-h"], ["--help"]):
        raise SystemExit(__doc__)
    commit = sys.argv[1] if len(sys.argv) > 1 else run("git", "rev-parse", "HEAD").strip()
    outcome = wait(script_tag(), commit)
    if outcome is None:
        print(f"no Workers Build for {commit[:8]} after {APPEAR}s; deploying site/ with wrangler")
        subprocess.run(
            ["npx", "wrangler@4", "deploy", "--config", "deploy/web/wrangler.jsonc"],
            check=True,
        )
        return 0
    print(f"Workers Build for {commit[:8]}: {outcome}")
    return 0 if outcome in ("success", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
