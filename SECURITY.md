# Security Policy

## Reporting a Vulnerability

**Please do not open a public GitHub issue for a security vulnerability.** That publishes the details before a fix exists.

Instead, use GitHub's private reporting: go to the [Security tab](https://github.com/xDarkzx/Audacity4-MCP/security) → **Report a vulnerability**. This opens a private conversation only you and the maintainer can see, and lets you attach details/reproduction steps without exposing them publicly.

## What to Expect

This is a solo-maintained, early-alpha project, so response times aren't guaranteed on a fixed SLA, but a genuine security report will be prioritized ahead of regular feature work. You'll get an acknowledgement, and a fix (or an explanation if it turns out not to be exploitable) once it's been looked into.

## Scope

Audacity4MCP runs locally and talks to a companion Audacity 4 fork over a plain TCP socket on `127.0.0.1` — there's no server, no cloud component, and no network exposure by design. Relevant reports include things like:

- A way for a malicious audio file, project file, or MCP tool call to trigger unintended file access, code execution, or data exfiltration
- Path traversal or injection through any tool parameter
- Anything that lets an MCP client do more than the documented tools allow
- Anything in the TCP bridge itself that would let a *different* local process interfere with the connection (e.g. hijack the port before Audacity binds it)

Reports about the underlying Audacity application, or about the `Audacity4-Dev` fork's C++ internals unrelated to the `src/mcp/` bridge module, belong with the [Audacity project](https://github.com/audacity/audacity) instead.

## Supported Versions

This is early alpha with no tagged releases yet. Only the current `main` branch is supported — please reproduce against the latest commit before reporting.
