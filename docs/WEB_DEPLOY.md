# Web publication boundary

The loopback viewer is the current supported web surface. Start it with:

```sh
npm run build:viewer
npm run engine -- serve
```

It is a read projection over `RunEngine.inspect` with a revision-safe human
inbox. It is not a generic file server or a second execution path.

Public or authenticated web publication is a pending product decision. If it is
introduced, it must consume only immutable artifacts named by a released
`ReleaseMachine` decision. It must not discover editions from directories,
rebuild legacy output, or treat a deployment manifest as workflow authority.

Sources and manuscripts are private by default. An exposed surface must have
authentication and authorization before it serves a private artifact. Public
distribution also requires explicit rights clearance for every source included
in the released edition.

The previous Cloudflare assembly design used the superseded Python workflow and
output tree. It is retained only as historical repository context. Do not run
its assembly script or deploy it to publish an engine run.
