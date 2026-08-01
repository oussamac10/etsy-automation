# Etsy PNG Automation — Claude Instructions

This package contains the durable instructions Claude Code needs to build the app phase by phase.

## Recommended repository structure

```text
etsy-png-automation/
├── CLAUDE.md
├── apps/
│   ├── web/CLAUDE.md
│   ├── api/CLAUDE.md
│   └── worker/CLAUDE.md
├── packages/
│   ├── domain/CLAUDE.md
│   └── image-pipeline/CLAUDE.md
├── infra/CLAUDE.md
├── tests/CLAUDE.md
└── docs/
    ├── API_COSTS.md
    └── PHASES.md
```

Copy these files into the matching paths of a new Git repository. Open the repository with Claude Code and begin with:

```text
Read CLAUDE.md and docs/PHASES.md completely. Start Phase 1 only. Implement it, run all required checks, update the phase checklist, and stop with a concise handoff. Do not start Phase 2.
```

The root `CLAUDE.md` applies everywhere. A nested `CLAUDE.md` adds rules for its own directory.

## Product decision already made

Build a private, single-shop MVP first. It creates Etsy drafts but never publishes automatically. After the private tool works reliably, multi-user SaaS support can be added as a separate phase.

