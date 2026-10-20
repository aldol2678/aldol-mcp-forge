# Security policy

## Supported scope
This v0.3.0 release is an offline-capable local HTML/ZIP QA runner. It is **not** a sandbox or a hosted MCP service.

## Threat model
Untrusted HTML/ZIP can contain code, oversized inputs, complex dependency graphs or browser exploit payloads. The script limits some archive structures and aborts browser HTTP routes but does not guarantee safe execution of arbitrary adversarial projects. Only run browser tests inside a credential-free, low-privilege OS/container with outbound network isolation and resource limits. Never grant production secrets, home directory access or cloud credentials. Do not run against third-party assets without permission.

## Reporting
Please use GitHub's private vulnerability reporting mechanism if enabled. Otherwise open a security issue without exploitable payloads or private credentials and request a private channel.

## Evidence
UNKNOWN is deliberately not success; do not infer real-device/production readiness from Playwright emulation. CI tests here cover Python self-test only and do not claim hostile code isolation.

## v0.4 MCP boundary

The remote HTTP adapter is single-owner and authenticated on every MCP request with a >=32-character secret. It refuses server filesystem paths, arbitrary URL downloads, browser Origin access and all HTML execution. Remote Docker contains no Chromium/Playwright. Network denial for arbitrary browser execution is **not verified**; remote browser tools therefore return blocked UNKNOWN. Never enable arbitrary remote code with the local operator opt-in.

Uploads use strict base64 and bounded ZIP parsing; no extraction onto host paths. Limits, TTL, ephemeral reports and process deadlines are described in README. Static checks spawn only Node's syntax parser with a minimal environment, never evaluate uploaded scripts. CPU, output and file-descriptor limits apply to workers; Docker/Railway applies remote service memory/CPU limits. Local execution is not an OS sandbox. An operator-controlled artifact directory must not be writable by other users (local symlink races are outside this single-owner model).

Do not embed owner credentials in plugin archives, GitHub, logs or MCP URLs. Use ChatGPT's API-key credential prompt or another client's secret manager. Rotate via the isolated Game Ops service only. One token grants access to all reports for that owner; this is not a multi-tenant service. Inspecting a game does not authorize publication, deletion, release or modification of that game.
