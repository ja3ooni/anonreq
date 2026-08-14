# Docs insert (insurance claims)

Raw `application/pdf` is **not** forwarded (the multimodal router keeps PDFs local). For the claims demo, extract text first, then send it through the same `/v1/chat/completions` path.

```bash
export ANONREQ_URL=http://localhost:8080
export ANONREQ_API_KEY=...

python3 submit_claim.py insurance-claim.de.txt
# or: pdftotext claim.pdf - | python3 submit_claim.py -
```

That is the “PDF upload” story without pretending the gateway OCRs PDFs.
