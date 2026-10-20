---
name: project-routing
description: Identify a game's actual development, version, QA, and delivery environment without assuming GitHub, a code repository, CI, or a common project infrastructure. Use before game QA, release decisions or agent handoffs whenever the current environment is not already established.
---

# ALDOL Project Routing

A game is an independent project until current evidence demonstrates shared ownership or build infrastructure. Never infer that it uses GitHub, Vercel, Unity, a certain host, or a shared repository merely because another ALDOL game does.

## Discover the minimal verified project profile
1. **Identity**: game name and explicit playable URL, local file, project page, build package or platform project ID, if available.
2. **Runtime**: web browser / mobile web / platform web runtime / Unity or native PC / other; distinguish authoring environment from player runtime.
3. **Development source**: local files, Git repository, no accessible source, platform-native editor or other system. Treat a platform snapshot, preview, clone or independent HTML port as distinct unless synchronization is proven.
4. **Version evidence**: actual build/version, file/hash, platform revision, runtime UI version or last verified deployment as appropriate. Never invent a SHA when none exists.
5. **Delivery path**: direct file, platform publish, repository+CI+deploy, store/package/manual install, or unknown. Only check gates that exist.
6. **Acceptance & authority**: applicable device/OS/browser target and current project-specific canonical rules, if material. Preserve per-game independence and user decisions.

Gather these from provided context and authorized read-only tools without demanding a rigid form. If essential fields remain missing, identify them as UNKNOWN; do not fabricate a repository, force migration, or conflate a proposal with a published build.

## Result
Produce a compact profile and explicitly select a relevant QA/release workflow: `local-artifact`, `platform-hosted`, `git-ci`, `native-client`, `web-runtime`, or `unknown`. Pathways may overlap. State observed facts vs assumptions and the evidence source.
