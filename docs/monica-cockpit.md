# Monica Cockpit Integration

Status: enabled by formal approval on 2026-10-15. `COCKPIT_MONICA_ENABLED=1` via systemd drop-in; default in code remains false for unblessed deployments.

## Embedding inside Clarity OS

- Use the same-origin route: `/cockpit/monica`.
- Prefer an iframe or native panel bound to the authenticated Clarity session.
- Do not inject Grafana admin credentials into the browser.
- Preserve the existing portal session and redirect to login on 401/403.
- Keep the embedded frame `sandbox="allow-scripts allow-same-origin"` only when required; avoid `allow-forms` unless the cockpit writes through the API require it.

## Adapter policy

- `token_optimiser/integration/monica_cockpit_adapter.py` is read-oriented.
- Mail remains read/draft only, no send/delete.
- Repo tasks are read-only; repository writes require approval.
- Arbitrary URLs are not proxyable; only allowlisted `cockpit_panels` rows that match the Grafana allowlist.

## Routes

- `GET /cockpit/monica`
- `GET /api/cockpit/monica/state`
- `GET /api/cockpit/monica/tasks`
- `POST /api/cockpit/monica/tasks`
- `GET /api/cockpit/monica/reminders`
- `POST /api/cockpit/monica/reminders`
- `GET /api/cockpit/monica/panels`
- `POST /api/cockpit/monica/panels`
- `GET /api/cockpit/monica/apm`

## Security

- Keep the generic client confined to portal-owned stores and allowlisted panels.
- Preserve the 55% security confidence ceiling for security-related cockpit actions.
- Do not provide broad OS control or command-execution from the cockpit.
