"""DSAR (Data Subject Access Request) workflow package.

Provides data subject erasure, processing restriction, and
full DSAR lifecycle management (submit → verify → fulfill).

Per D-021 through D-025:
- D-021: DSAR intake, verification, fulfillment with status tracking
- D-022: Data subject erasure (Valkey mapping deletion)
- D-023: Data subject restriction (block future requests)
- D-024: Legal Hold interception for erasure requests
- D-025: Subject status tracking (deleted, processing_restricted, legal_hold)
"""
