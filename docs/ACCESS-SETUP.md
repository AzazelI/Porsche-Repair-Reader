# Access setup — protecting the Repair Reader

The frontend contains **no credentials and no login check**. It cannot: this is a static
site, so every file the browser needs is a file any visitor can download. The previous
version compared a hardcoded email and password inside `frontend/app.js`, which meant the
password was published to anyone who opened DevTools or read the public Git history.

Authentication now happens one layer up, at the Cloudflare edge, before `index.html` is
ever sent. Until you complete the steps below, the deployed site shows an
**"Access policy not configured"** screen and refuses to open the cockpit.

---

## 1. Enable Cloudflare Access on the Pages project

Free for up to 50 users on the Cloudflare Zero Trust free plan.

1. Cloudflare dashboard → **Zero Trust** → **Access** → **Applications** → **Add an application**
2. Type: **Self-hosted**
3. Application domain: `porsche-repair-reader.pages.dev`
   - To also cover preview deployments, add a second hostname: `*.porsche-repair-reader.pages.dev`
4. Session duration: `24 hours` is a reasonable default for workshop use.
5. **Add a policy**
   - Name: `Tegeta technicians`
   - Action: **Allow**
   - Include → **Emails** (list each technician), or **Emails ending in** → `@tegeta.ge`
6. Identity provider: **One-time PIN** works with zero setup — the user receives a code by
   email. Google / Microsoft Entra SSO are better if Tegeta already has one.
7. Save.

Verify: open the site in a private window. You should land on the Cloudflare login screen,
**not** on the Porsche splash. After signing in, the splash shows
`Authenticated as <your email>` in green.

Repeat the same steps for `porsche-planner-tegeta.pages.dev`.

---

## 2. How the frontend reads the result

`frontend/app.js` calls the edge endpoint Cloudflare exposes to applications behind Access:

| Endpoint | Meaning |
| --- | --- |
| `GET /cdn-cgi/access/get-identity` → `200` + JSON | Visitor verified; `identity.email` is displayed |
| `GET /cdn-cgi/access/get-identity` → `404` | No Access policy on this hostname |
| `/cdn-cgi/access/logout` | Ends the Access session (wired to the footer sign-out link) |

Four states follow from that:

- **checking** — request in flight
- **ready** — identity verified, "Enter Cockpit" enabled
- **dev** — `localhost` / `127.0.0.1` / `file://`, gate skipped with a visible warning
- **blocked** — public hostname, no Access policy → cockpit stays closed

The **blocked** screen is an operator warning, not a security control. It hides the UI, but
the HTML, CSS, and JS are still downloadable, and the backend API is still reachable. Real
protection begins only once step 1 is done and Cloudflare stops serving the page at all.

---

## 3. Still open — not fixed by this change

- **The leaked password lives in Git history.** `github.com/AzazelI/Porsche-Repair-Reader`
  is public, so removing the line from the current file does not remove it from past
  commits. Treat that password as permanently compromised and rotate it everywhere it was
  reused. Scrubbing history requires `git filter-repo` plus a force-push and coordination
  with anyone who has a clone — a deliberate decision, not a side effect of this change.
- **The backend has no user authentication.** `https://azazei-porsche-repair-reader.hf.space`
  accepts uploads from anyone who knows the URL, and each request spends Gemini quota.
  Access protects the frontend, not the API. Closing this needs either a shared secret
  header checked in `backend/main.py`, or moving the API behind Cloudflare too.
- **`ALLOWED_ORIGINS` still defaults to `*`.** Set it on the Hugging Face Space to the two
  Pages origins so the API stops accepting cross-origin calls from arbitrary sites.
