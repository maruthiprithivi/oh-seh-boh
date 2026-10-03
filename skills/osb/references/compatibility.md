# Installation and compatibility

Source-only package; no harness installed, invoked or behaviorally tested. Research below establishes documented native discovery, not compatibility certification. Confirm the product meant by `omp` and `agy` before choosing their rows. Use only canonical frontmatter `name` and `description`; no harness-specific hooks/tool names are required by the skill ([Agent Skills specification](https://agentskills.io/specification)).

Copy the **whole** `osb` folder into one chosen project skill root, then use that harness's skill picker or explicit invocation. Do not install across all roots, overwrite existing skills, or assume symlinks work everywhere. Use personal roots only when the user explicitly chooses cross-project availability. This document is an installation adapter; it performs no installation.

| Requested harness | Documented project root | Personal root / caveat | Status and source |
|---|---|---|---|
| omp, if Oh My Pi | `.omp/skills/osb` | `~/.omp/agent/skills/osb`; compatible roots also scanned | Documented, not runtime tested; [skills](https://github.com/can1357/oh-my-pi/blob/main/docs/skills.md) |
| Claude Code | `.claude/skills/osb` | `~/.claude/skills/osb`; cloud requires repository-visible source | Documented, not runtime tested; [skills](https://code.claude.com/docs/en/skills) |
| Codex | `.agents/skills/osb` | `~/.agents/skills/osb`; project ancestor scan | Documented, not runtime tested; [skills](https://learn.chatgpt.com/docs/build-skills) |
| OpenCode | `.opencode/skills/osb` | `~/.config/opencode/skills/osb`; `.agents`/`.claude` compatibility | Documented, not runtime tested; [skills](https://opencode.ai/docs/skills/) |
| Cursor | `.cursor/skills/osb` or `.agents/skills/osb` | Verify installed editor/CLI version and root precedence | Documented native support, not runtime tested; [skills](https://prod.cursor.com/docs/skills), [2.4](https://cursor.com/changelog/2-4) |
| agy, if Google Antigravity CLI | `.agents/skills/osb` | `~/.gemini/antigravity-cli/skills/osb` | Product identity conditional; documented, not runtime tested; [CLI install](https://www.antigravity.google/docs/cli/install/) |
| Antigravity IDE | Confirm installed-version project root | `~/.gemini/config/skills/osb`; distinct from CLI | Personal root documented, project discovery unverified here; [skills](https://antigravity.google/docs/skills?app=antigravity-ide) |
| kiro-cli | `.kiro/skills/osb` | `~/.kiro/skills/osb`; version/custom-agent resource inheritance matters | Documented, not runtime tested; [skills](https://kiro.dev/docs/skills/), [CLI 1.24](https://kiro.dev/changelog/cli/1-24/), [CLI 2.1](https://kiro.dev/changelog/cli/2-1/) |
| Kiro IDE | `.kiro/skills/osb` | `~/.kiro/skills/osb` | Documented, not runtime tested; [skills](https://kiro.dev/docs/skills/) |
| Kimi Code CLI | `.agents/skills/osb` shared root preferred | Product docs differ on `.kimi-code`, `.kimi` and `KIMI_CODE_HOME`; inspect installed version | Shared root documented, version-specific roots unverified; [hosted docs](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html), [repository docs](https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/customization/skills.md) |
| Other or unresolved omp/agy | No asserted root | Read approved absolute `SKILL.md` path manually and follow references | Manual workflow only until product/version confirmed |

Before enabling mutations, produce a read-only doctor report: actual product/version, discovered skill path, loaded reference path, backend mode/version and client/gate version, authenticated principal (no tokens), immutable repository/team scope, authority epoch, enforcement boundary and permitted mutation operations. If any value cannot be verified, report it as unknown and keep mutations disabled. Manual loading requires the same checks.

For workflow continuity, propose a short project instruction in the harness's existing approved instruction file: “Before repository work, load osb and join/resume the configured ledger; before shared mutations verify the current claim; record handoff/completion evidence.” Do not overwrite unrelated instructions or modify global config. This prompt reminder is not guaranteed enforcement. Reliable always-on use requires separately reviewed deterministic commands/gates; harness hooks differ and are not a universal security boundary.
