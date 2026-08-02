# Archived web-deployment scaffold

This directory contains a frozen Cloudflare deployment experiment from the
superseded Python workflow. It is not connected to `RunEngine` and must not be
used to publish, preview, or advance an engine run.

The supported browser surface is the loopback viewer:

```sh
npm run build:viewer
npm run engine -- serve
```

Any future hosted publication must be designed as a consumer of exact released
engine artifacts, with authentication and source-rights authorization decided
before deployment. It must preserve the engine's immutable artifact and release
authority boundaries.
