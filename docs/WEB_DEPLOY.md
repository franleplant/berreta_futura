# Web publication boundary

`mag render NNN` writes the web edition from Rust alongside the PDFs:
`editions/NNN/render-*/en/web-output.zip` (paged HTML, fonts, assets) and the
release `package.zip`. Nothing serves it; there is no viewer process.

`deploy/web/` holds an undeployed Cloudflare scaffold, access-gated first.
Public or authenticated publication is a pending product decision. If it is
introduced, it serves only a finished render's web output, never the library,
runs, or `.magazine/` scratch.

Sources and manuscripts are private by default. An exposed surface must have
authentication and authorization before it serves a private artifact.
