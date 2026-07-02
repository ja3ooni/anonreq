# Superpowers Setup for AnonReq v4

## Scope

This setup is intentionally limited to the V4 product scope and does not require changes to the existing GSD planning workspace under .planning.

## What Superpowers gives you

Superpowers adds an agent workflow based on:
- brainstorming
- planning
- execution
- test-driven development
- review
- branch finishing

This is useful for V4 work such as governance, compliance automation, trust center, document workflows, and agent governance.

## Recommended approach

Use Superpowers as a workflow layer for V4 work only:
- keep all V4 planning and backlog artifacts in req/v4
- keep GSD planning artifacts unchanged under .planning
- use Superpowers to help structure implementation and review work for V4 features

## Installation options

Choose the option that matches your coding agent.

### Claude Code
Run:

```bash
/plugin install superpowers@claude-plugins-official
```

### Cursor
In Agent chat, run:

```text
/add-plugin superpowers
```

### GitHub Copilot CLI
Run:

```bash
copilot plugin marketplace add obra/superpowers-marketplace
copilot plugin install superpowers@superpowers-marketplace
```

### Codex CLI
Open the plugin UI and install Superpowers from the marketplace.

## Suggested V4 prompt

When working on V4 scope, start with a prompt like this:

```text
For the V4 scope in req/v4, use the Superpowers workflow:
1. brainstorm the feature
2. write a clear implementation plan
3. execute the plan in small steps
4. follow TDD where practical
5. request code review before finalizing
Do not change the GSD planning workspace under .planning.
```

## Suggested working pattern

For each V4 epic or feature:
1. brainstorm the requirement
2. produce a short plan in req/v4
3. implement in small slices
4. verify with tests or checks
5. request review before completion

## Practical rule for this repo

Keep V4 work in:
- req/v4/FEATURE_SET.md
- req/v4/ROADMAP.md
- req/v4/PRD.md
- req/v4/BACKLOG.md
- req/v4/SUPERPOWERS_SETUP.md

Do not use Superpowers to modify the GSD planning structure under .planning.
