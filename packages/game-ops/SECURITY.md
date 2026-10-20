# Security policy

## Supported scope
This v0.3.0 release is an offline-capable local HTML/ZIP QA runner. It is **not** a sandbox or a hosted MCP service.

## Threat model
Untrusted HTML/ZIP can contain code, oversized inputs, complex dependency graphs or browser exploit payloads. The script limits some archive structures and aborts browser HTTP routes but does not guarantee safe execution of arbitrary adversarial projects. Only run browser tests inside a credential-free, low-privilege OS/container with outbound network isolation and resource limits. Never grant production secrets, home directory access or cloud credentials. Do not run against third-party assets without permission.

## Reporting
Please use GitHub's private vulnerability reporting mechanism if enabled. Otherwise open a security issue without exploitable payloads or private credentials and request a private channel.

## Evidence
UNKNOWN is deliberately not success; do not infer real-device/production readiness from Playwright emulation. CI tests here cover Python self-test only and do not claim hostile code isolation.
