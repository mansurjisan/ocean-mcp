# Security Policy

Ocean-MCP is an early-stage, actively-developed project. This policy
reflects that: it's short, and it doesn't claim more process maturity than
actually exists.

## Reporting a vulnerability

Please report suspected vulnerabilities privately using GitHub's private
vulnerability reporting, rather than filing a public issue:

**https://github.com/mansurjisan/ocean-mcp/security/advisories/new**

There is no dedicated security email for this project — use the link
above. Include the affected server(s), a description of the issue, and
reproduction steps if possible. This is a small project maintained without
a formal SLA, but reports will be acknowledged and worked as soon as
practical.

## Scope

Ocean-MCP publishes 19 independently installable MCP servers, most of
which are read-only clients over free public NOAA/ocean data APIs and
require no credentials. The primary security-relevant surface is
different:

- **`hpc-system-mcp`** and **`ufs-runner-mcp`** are the two servers that
  execute commands rather than just fetch data — they submit and monitor
  jobs on NOAA RDHPCS HPC systems (Slurm/PBS), and `ufs-runner-mcp` also
  stages files. Input handling, command construction, and any sandboxing
  or injection-hardening around these two servers is explicitly in scope
  and the area we'd most want a report about.
- The remaining servers are read-only data clients (CO-OPS, ERDDAP, NHC,
  Recon, STOFS, OFS, RTOFS, WW3, NDBC, USGS, winds, GOES, ADCIRC, SCHISM,
  and others) with no API keys and no write access to any upstream system.
  Vulnerabilities in how they parse or handle untrusted upstream API
  responses are still in scope, just lower severity than command execution
  paths.
- The publishing pipeline: all PyPI packages are published via GitHub OIDC
  trusted publishing (no long-lived tokens in the repo). Issues with the
  publish workflow or its permissions are in scope.

## Supported versions

Every server in this repo is currently at a `0.1.x` version. There is no
long-term-support policy yet — only the latest published version of each
server's PyPI package receives fixes. If you depend on one of these
servers, pin a version and expect to need to upgrade rather than backport.

## Disclosure

Please give us a reasonable window to investigate and, where applicable,
publish a fix before any public disclosure. We'll coordinate timing with
you on the advisory.
