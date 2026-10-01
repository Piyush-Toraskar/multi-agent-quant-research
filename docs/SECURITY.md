# Security and deployment boundary

This is local, single-user research software. Bind it to loopback and do not expose it directly to the
internet, a shared LAN or a tunnel. There is no user authentication, tenancy boundary or per-user storage.
The Docker mapping also publishes only on 127.0.0.1. Host/origin checks are supplementary, not authentication.

Implemented safeguards include bounded/validated request fields, a bounded queue and agent loop,
allow-listed tools, exact experiment-argument checks for LLM calls, parameterised SQL, no generic
SQL endpoint, content-addressed files with identifier validation and hash checks, delayed execution,
explicit real/synthetic provenance, HTML text rendering for untrusted strings, a restrictive CSP,
no embedded secrets and no arbitrary Python/shell tool. LLM endpoint errors redact configured secrets.

Tool services receive necessary data/database configuration but not LLM API keys through the generated
child environment. They still execute as the local operating-system user and can access the filesystem
under that identity. MCP stdio and Docker do not turn them into hardened untrusted-code sandboxes.
Only trusted application functions execute; model-generated code is never run.

Provider payloads include the research request and relevant computed data. Enabling a remote model
therefore sends that information to its operator. Choose a suitable provider and review its data terms.
The project makes no claim about external model retention, market-data redistribution rights, current
service pricing or financial regulation.

Before any multi-user deployment, implement authentication, per-user authorisation and isolation,
TLS, rate limiting, durable jobs, migrations, monitoring, secret management, backups and retention rules.
