# Custom E2B sandbox image (verified regression)

Verified regression uses **statsmodels**, which the default E2B code-interpreter
image doesn't include. Two ways this is handled:

1. **Now (works out of the box):** the regression templates self-install
   statsmodels once per sandbox (paid once per session, ~15–30s on the first
   regression). No setup needed.

2. **Better (recommended for production):** build a custom image with statsmodels
   preinstalled, so there's no per-session install. Steps below.

## Build & publish the custom image

Requires the E2B CLI and your E2B account:

```bash
npm i -g @e2b/cli            # or: pipx install e2b
e2b auth login

cd backend/e2b
e2b template build           # builds from e2b.Dockerfile, prints a template id
```

`e2b template build` creates/updates an `e2b.toml` here with the generated
`template_id`. Then point the backend at it:

```bash
# backend/.env
E2B_TEMPLATE=<template_id_from_build>
```

Restart the backend. `sandbox/manager._create_sandbox` will create sandboxes from
this image (and safely fall back to the default image if the template is ever
unavailable).

## Verifying

- Golden tests validate the regression LOGIC locally (they don't touch E2B):
  `cd backend && pytest tests/test_regression_golden.py -q`
- Live check: upload a dataset and ask e.g. "predict <numeric> from <a> and <b>".
  With the custom image the first regression is instant; without it, the first
  one pauses ~15–30s while statsmodels installs, then works.

## Notes
- If E2B changes the base image tag, update `FROM` in `e2b.Dockerfile`.
- Keep the statsmodels version in sync with `requirements.txt` / the golden tests.
