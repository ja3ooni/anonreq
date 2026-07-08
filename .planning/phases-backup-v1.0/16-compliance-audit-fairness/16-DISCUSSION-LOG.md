# Phase 16: Compliance, Audit & Fairness - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-06-20
**Phase:** 16-compliance-audit-fairness
**Areas discussed:** Fairness Testing, Post-Deploy Monitoring, Data Lineage, Legal Hold, Data Subject Rights, Breach Notifications, Incident Classification, Retention, eDiscovery, Datasets, Provider Review

---

## Fairness Testing
**User's choice:** CI/CD + monitoring.

## Post-Deploy Monitoring
**User's choice:** Extends Phase 11 SLO framework.

## Data Lineage
**User's choice:** PostgreSQL + MinIO archive.

## Legal Hold
**User's choice:** Tenant-level + record-level tagging.

## Data Subject Rights
**User's choice:** DSAR → retention check → no hold = delete mapping, hold = restrict processing. subject_status: { deleted, processing_restricted, legal_hold }.

## Breach Notifications
**User's choice:** Governance records + escalation path.

## Incident Classification
**User's choice:** Critical (immediate), High (24h), Medium (72h), Low (next review).

## Retention
**User's choice:** PostgreSQL 90d, MinIO WORM 7y, Valkey TTL, Legal Hold infinite.

## eDiscovery
**User's choice:** JSONL + PDF + EDRM XML.

## Fairness Datasets
**User's choice:** MinIO bucket by hash with metadata (id, sha256, owner, approved_by, approval_date, framework, version).

## Provider Review
**User's choice:** Phase 14 lifecycle + 365d review + risk re-evaluation triggers (model change, ToS, data residency, AI Act, security incident).
