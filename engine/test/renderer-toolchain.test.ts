import assert from "node:assert/strict";
import { chmod, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  inspectRendererToolchain,
  probeRendererToolchain,
} from "../renderer-adapter/toolchain.ts";

async function fixture(): Promise<{ readonly root: string; readonly uv: string; readonly python: string }> {
  const root = await mkdtemp(join(tmpdir(), "mag-renderer-toolchain-"));
  const uv = join(root, "uv");
  const python = join(root, "python");
  await writeFile(uv, "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then printf 'uv fixture-1\\n'; exit 0; fi\nexit 0\n", "utf8");
  await writeFile(python, `#!/bin/sh
printf '%s' '{"pythonVersion":"3.12.11","pythonImplementation":"CPython","pythonCacheTag":"cpython-312","platform":"${process.platform}-${process.arch}"}'
`, "utf8");
  await chmod(uv, 0o700);
  await chmod(python, 0o700);
  return { root, uv, python };
}

test("toolchain probe rejects configured symlink executables", async () => {
  const f = await fixture();
  try {
    const linkedUv = join(f.root, "linked-uv");
    await symlink(f.uv, linkedUv);
    await assert.rejects(
      inspectRendererToolchain(linkedUv, f.python),
      /uv executable must be a regular non-symlink/u,
    );
  } finally {
    await rm(f.root, { recursive: true, force: true });
  }
});

test("toolchain probe rejects replacement of an approved executable", async () => {
  const f = await fixture();
  try {
    const expected = await inspectRendererToolchain(f.uv, f.python);
    await writeFile(f.uv, "#!/bin/sh\nprintf 'uv replacement\\n'\n", "utf8");
    await chmod(f.uv, 0o700);
    await assert.rejects(
      probeRendererToolchain({ uvExecutable: f.uv, pythonExecutable: f.python, expected }),
      /uvSha256/iu,
    );
  } finally {
    await rm(f.root, { recursive: true, force: true });
  }
});

