# V4 Working Agreement

## Purpose

This document defines how V4 work should be organized in this repository without interfering with the existing GSD planning artifacts.

## Allowed V4 planning files

V4 planning and product work may be created or updated in:
- req/v4/V4_FEATURE_SET.md
- req/v4/ROADMAP.md
- req/v4/PRD.md
- req/v4/BACKLOG.md
- req/v4/SUPERPOWERS_SETUP.md
- req/v4/WORKING_AGREEMENT.md

## Files that must remain untouched

The following areas are reserved for the existing planning and workflow system and should not be modified for V4-specific product planning unless explicitly approved:
- .planning/
- phases/
- req/requirements.md
- req/requirements_v2.md
- req/PRD.md
- req/HLD.md
- req/LLD.md
- req/ROADMAP.md

## Rule of separation

V4 scope should be treated as a product and execution layer for future work, while the existing planning structure remains the baseline system of record.

## How to use Superpowers in this repo

Superpowers may be used to help structure V4 implementation work, but it should be applied only to the V4 scope.

Recommended pattern:
1. Use V4 planning files under req/v4 as the source of truth for V4 scope.
2. Use Superpowers to help brainstorm, plan, execute, and review V4 features.
3. Keep implementation notes and feature-specific planning inside req/v4 or a V4-specific subfolder if later needed.
4. Do not use Superpowers workflows to alter .planning artifacts or existing GSD planning structure.

## Working conventions

- Keep V4 work focused on product scope, architecture decisions, backlog refinement, and implementation planning.
- Prefer small, explicit updates over broad restructuring.
- If a change could affect the core GSD planning system, pause and confirm before making it.

## Decision rule

If a task is about the existing GSD planning workflow, keep it out of V4 scope.
If a task is about V4 product direction, implementation planning, or execution support, place it under req/v4.
