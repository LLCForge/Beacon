# Security Policy

Beacon runs close to network infrastructure, so we take security reports seriously and appreciate responsible disclosure.

## Supported versions

| Version | Supported |
|---|---|
| Latest release | Yes |
| `main` branch | Yes (best effort) |
| Older releases | No, please upgrade |

## Reporting a vulnerability

**Do not open a public issue, discussion or pull request for security problems.**

Report privately through GitHub Security Advisories:

1. Go to [https://github.com/LLCForge/Beacon/security/advisories/new](https://github.com/LLCForge/Beacon/security/advisories/new).
2. Describe the issue, affected version or commit, and steps to reproduce.
3. Include a proof of concept if you have one. Strip any real customer data, IP addresses or credentials from captures and logs.

What to expect:

- Acknowledgement within **3 business days**.
- An initial assessment and severity rating within **10 business days**.
- A fix or mitigation plan, coordinated disclosure date, and credit in the advisory (unless you prefer to stay anonymous).

## In scope

- Secret leakage: webhook/HMAC secrets, bot tokens, SMTP credentials, PagerDuty/Opsgenie keys appearing in logs, alerts, errors or the persistent queue.
- Injection through alert fields into Telegram HTML, Slack/Discord/Teams payloads, e-mail headers (header injection) or syslog frames.
- Webhook signature bypass or replay (HMAC verification, timestamp window).
- Authentication bypass on the silences, reload or health APIs.
- Persistent queue corruption, unbounded growth or crash on a torn / hostile queue file.
- Dependency vulnerabilities reachable from Beacon's code paths. Because every LLCForge tool vendors Beacon, a Beacon advisory is coordinated across all six tools.

## Out of scope

- Vulnerabilities in third-party services or protocols themselves (report those upstream).
- Issues that require an attacker to already control the host or the config file.
- Denial of service by volumetric flooding of the network the tool runs on.

## Attack surface

| Surface | Default | Protection |
|---|---|---|
| BMP collector | `0.0.0.0:11019` | source allowlist, 128 KiB message cap, bounded channel |
| Passive BGP listener | off (`collector.bgp`) | peer address allowlist, ASN check, hold timer, 64 KiB message cap; no TCP-MD5 |
| Route API + web UI | `127.0.0.1:8180` | read-only, optional bearer token, CSP / `nosniff` / `DENY` framing, 64 concurrent requests, 10 s timeout, result caps |
| Management (`/metrics`, health, silences, reload) | off until `[metrics] listen` is set | silences / reload need bearer tokens; metrics and health are unauthenticated |
| Notary client | off until `[notary]` is set | outbound only, no redirects, timeout, response size / value checks |
| MRT import, relationship file | local files | size caps (16 MiB per MRT record, 256 MiB relationship file), skip-on-error |

## Hardening recommendations

- Run as an unprivileged user; grant only the capabilities the tool needs (`CAP_NET_BIND_SERVICE` only if the passive BGP listener uses port 179).
- Bind the management and API listeners to localhost or a management network, and set `api.token_env` when the API is reachable by others.
- Restrict the BMP and BGP ports to your routers with a firewall; the passive BGP session has no TCP-MD5.
- Keep secrets in environment variables or your secret manager, never in the config file or in version control.
