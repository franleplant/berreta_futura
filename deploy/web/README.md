# Public web site

`.github/workflows/site.yml` builds `mag`, runs `mag site --out output/site`
from committed state, and on every push to `main` (or a manual run) deploys
that directory to https://berreta.franleplant.com as Cloudflare Workers static
assets. Pull requests build the site and stop before deploying. CI never
renders a PDF: `mag site` reads `edition.yaml`, the committed run, and library
media, and PDF links come from `editions/NNN/publish.yaml`.

`wrangler.jsonc` is assets-only: no Worker script, no `workers.dev` URL, the
custom domain attached by `routes`, and unknown paths answered by the nearest
`404.html` with status 404. Cloudflare caps each asset at 25 MiB and a version
at 20,000 files on the free plan; the workflow fails before deploying if
`output/site` holds a file over 25 MiB or no `404.html`.

## One-time setup

1. Account ID: Cloudflare dashboard, open any zone (franleplant.com), copy
   **Account ID** from the right-hand column of the Overview page.
2. API token: dashboard, profile icon, **My Profile**, **API Tokens**,
   **Create Token**, template **Edit Cloudflare Workers**, **Use template**.
   Keep its permissions and make sure the list reads:
   - Account, Workers Scripts, Edit
   - Account, Account Settings, Read
   - Zone, Workers Routes, Edit
   - Zone, Zone, Read
   - Zone, DNS, Edit (add it: the custom domain creates its DNS record)
   - User, User Details, Read and User, Memberships, Read (from the template)

   Under **Account Resources** pick your account; under **Zone Resources**
   pick **Specific zone**, `franleplant.com`. **Continue to summary**,
   **Create Token**, copy the token (it is shown once).
3. GitHub: repository **Settings**, **Secrets and variables**, **Actions**,
   **New repository secret**, twice:
   - `CLOUDFLARE_API_TOKEN`: the token from step 2
   - `CLOUDFLARE_ACCOUNT_ID`: the ID from step 1
4. Remove any existing DNS record for `berreta.franleplant.com` in the zone;
   the custom domain refuses to attach over one.
5. Push to `main` or run the workflow from the **Actions** tab. The first
   deploy creates the Worker `berreta-futura-web` and the custom domain.

## Local check

```sh
mag/target/release/mag site --out output/site
npx wrangler@4 deploy --dry-run --config deploy/web/wrangler.jsonc
```
