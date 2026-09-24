# Web publication boundary

The loopback viewer is the current supported web surface. Start it with:

```sh
npm run build:viewer
npm run engine -- serve
```

It is a read projection over `RunEngine.inspect` with a revision-safe human
inbox. It is not a generic file server or a second execution path.

Public or authenticated web publication is a pending product decision. If it is
introduced, it must consume only immutable artifacts authorized by the exact
current `RunEngine` decision. It must not discover editions from directories,
rebuild output, or treat a deployment manifest as workflow authority.

Sources and manuscripts are private by default. An exposed surface must have
authentication and authorization before it serves a private artifact.

`mag render` typesets with the native typst engine by default
(`magazine.toml [render] engine`, overridable per run with `--engine`), and a full
render writes the web edition from Rust. The Python WeasyPrint
renderer stays reachable through `--engine weasyprint` as the rollback.

`inputs/` and `durable/` are Git-tracked immutable revisions. `.magazine/` is
ignored runtime storage and `output/` is ignored, ephemeral exported material.
For edition `004`, each run uses the engine-generated
`<UTC timestamp>--<RunId>` root under `.magazine/004/`, with a matching
`output/004/` root only when an authorized export is produced.
