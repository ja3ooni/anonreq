# Bulgarian locale (`bg-BG`)

Send `X-AnonReq-Locale: bg` or `bg-BG` (or `bg,en`) to add the Bulgarian
recognizer bundle (`config/locales/bg-BG.yaml`) to the universal `en` bundle.
Checksums live in `src/anonreq/locale/checksums/bulgaria.py`. A bare
language code resolves to that language's only regional bundle (`bg` ->
`bg-BG`, `de` -> `de-DE`); other regions such as `de-AT` are still rejected.

| Entity | Shape | Validation | Masked as |
| --- | --- | --- | --- |
| EGN (ЕГН) | 10 digits, `YYMMDD` + serial + check | Real birth date (month +20 for 1800s, +40 for 2000s) and weights 2,4,8,5,10,9,7,3,6 mod 11 (10 → 0) | `EGN`; failures `EGN_UNVERIFIED` (0.6) when labelled (ЕГН/EGN) or when the digits hold a plausible 1900s/2000s birth date |
| LNCh (ЛНЧ) | 10 digits | Weights 21,19,17,13,11,9,7,3,1 mod 10 | `LNCH`; failures `LNCH_UNVERIFIED` when labelled (ЛНЧ/LNCh) |
| EIK / BULSTAT (ЕИК / БУЛСТАТ) | 9 digits, 13 for a branch, optional `BG` VAT prefix | 9: weights 1..8, fallback 3..10, mod 11. 13: plus digits 9-12 with 2,7,3,5, fallback 4,9,5,7 | `EIK`; failures `EIK_UNVERIFIED` when labelled (ЕИК/БУЛСТАТ/EIK/BULSTAT/ДДС/UIC) |
| IBAN | `BGkk` + 4-letter bank code + 14 alphanumerics (22) | ISO 13616 MOD-97 | `IBAN_BG`; lowercase or failing `IBAN_BG_UNVERIFIED` |
| ID card (лична карта) | 9 digits (cards before 17 June 2024) or 2 letters + 7 digits (current card) | No public checksum | `BG_ID_CARD`, only after a context word (лична карта, л.к., ЛК, ID card, документ за самоличност) |
| Phone | `+359`/`00359`, mobile 87/88/89/98/99, Sofia 2, other area codes; national `0…` | Format | `PHONE_BG`; without the trunk 0 only after тел./GSM/мобилен |

Checksum-typed candidates are validated in `RegexDetector` before overlap
resolution, so an invalid EGN cannot take the span from a valid LNCh or
phone number covering the same digits. Format-only failures are masked at
0.6 confidence (fail closed), like the German IBAN and Steuer-ID.

## Names and addresses

Not covered. `bg` is not in `ANONREQ_PRESIDIO_LANGUAGES`, so `bg-BG`
requests are analyzed with the English model and counted on
`anonreq_presidio_unsupported_locales_total{locale="bg-BG"}`. The English
model finds almost no Cyrillic names. Options for a later Presidio
`bg` engine:

| Option | Entities | Notes |
| --- | --- | --- |
| spaCy official | none | spaCy has a `bg` tokenizer but no trained Bulgarian pipeline. |
| spaCy `xx_ent_wiki_sm` | PER, LOC, ORG, MISC | Trained on WikiNER (no Bulgarian); weak on Cyrillic. Not recommended. |
| Stanza `bg` (BSNLP 2019) | PER, LOC, ORG, EVT, PRO | F1 83.2. Presidio supports Stanza through `spacy-stanza`. Apache-2.0 code. |
| CLASSLA `bg` (BulTreeBank) | PER, LOC, ORG, MISC | Stanza fork with rule-based tokenizer; model CC BY-SA 4.0. |
| Transformers (`rmihaylov/bert-base-ner-theseus-bg`, `auhide/bert-base-ner-bulgarian`) | PER, LOC, ORG | Presidio `TransformersNlpEngine`. Check each model's license and evaluate on business text; WikiANN-trained scores are optimistic. |
| `sakelariev/bg_news_trf` (spaCy) | NER | CC BY-NC-SA: not usable commercially. |
