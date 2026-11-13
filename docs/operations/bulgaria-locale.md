# Bulgarian locale (`bg-BG`)

Send `X-AnonReq-Locale: bg` or `bg-BG` (or `bg,en`) to add the Bulgarian
recognizer bundle (`config/locales/bg-BG.yaml`) to the universal `en` bundle.
Checksums live in `src/anonreq/locale/checksums/bulgaria.py`. A bare
language code resolves to that language's only regional bundle (`bg` ->
`bg-BG`, `de` -> `de-DE`); other regions such as `de-AT` are still rejected.

> **Live `bg` traffic is NOT cleared for personal data such as names and
> addresses until Bulgarian NER lands.** `bg-BG` masks the structured
> identifiers below only. Bulgarian text is analysed with the English NER
> model, which misses most Cyrillic names and addresses, so they reach the
> provider. Every `bg-BG` request is marked: the anonymization audit event
> carries `ner_coverage: structured_only` and the response carries
> `X-AnonReq-NER-Coverage: structured_only` (streaming and non-streaming,
> error responses including post-forward 503/504, the reverse and
> transparent proxy paths, and `/v1/debug/anonymize-preview`).

## Opt-in: `ANONREQ_BG_STRUCTURED_ONLY`

The gateway fails closed for `bg-BG` by default. A request whose negotiated
locales include `bg-BG` (`bg`, `bg-BG`, `en, bg`, ...) is refused before
anything is forwarded:

```http
HTTP/1.1 422 Unprocessable Entity
X-AnonReq-NER-Coverage: structured_only

{"error": {"type": "locale_not_cleared", "code": "bg_ner_not_cleared", ...}}
```

Set `ANONREQ_BG_STRUCTURED_ONLY=true` only when the operator has accepted
structured-ID-only masking (names and addresses reach the provider). The
flag is read when the pipeline is built and cached in `app.state`, so a
change needs a process restart; editing `.env` or the environment is not
enough on its own. The audit event records the decision as
`bg_structured_only: true|false` next to `ner_coverage`, for served and
refused requests. The admin preview applies the same gate, so it shows
what live traffic would get. Other locales are not affected.

The bundle's regexes are generated: edit `scripts/bg_locale/bg-BG.yaml.tpl`
or the label lists in `scripts/bg_locale/generate.py`, then run
`python scripts/bg_locale/generate.py` (a unit test fails if the YAML is
stale). Synthetic test values come from the `generate_*` helpers in
`bulgaria.py`.

Application logs are scrubbed fail-closed, alongside the de-DE identifiers:

- with no checksum gate: labelled EGN, LNCh and EIK/BULSTAT (ЕГН/EGN,
  ЛНЧ/LNCh, ЕИК/БУЛСТАТ/EIK/BULSTAT/ДДС/UIC ...), even when the checksum
  fails; any BG-IBAN-shaped value in any case and either shape below;
  `BG_ID_CARD` after its context word (`лична карта № AB1234567`); and
  `PHONE_BG`;
- checksum-gated, unlabelled numbers only: a 10-digit value is redacted
  only when it passes the EGN check (checksum plus birth date). Unlabelled
  LNCh and EIK/BULSTAT stay readable even when they happen to pass those
  checksums, so ordinary 9- and 10-digit counters, Unix timestamps and
  batch numbers are not over-redacted.

| Entity | Shape | Validation | Masked as |
| --- | --- | --- | --- |
| EGN (ЕГН) | 10 digits, `YYMMDD` + serial + check | Real birth date (month +20 for 1800s, +40 for 2000s) and weights 2,4,8,5,10,9,7,3,6 mod 11 (10 → 0) | `EGN`; failures `EGN_UNVERIFIED` (0.6) when labelled (ЕГН/EGN) or when the digits hold a plausible 1900s/2000s birth date |
| LNCh (ЛНЧ) | 10 digits | Weights 21,19,17,13,11,9,7,3,1 mod 10 | `LNCH`; failures `LNCH_UNVERIFIED` when labelled (ЛНЧ/LNCh) |
| EIK / BULSTAT (ЕИК / БУЛСТАТ) | 9 digits, 13 for a branch, optional `BG` VAT prefix | 9: weights 1..8, fallback 3..10, mod 11. 13: plus digits 9-12 with 2,7,3,5, fallback 4,9,5,7 | `EIK`; failures `EIK_UNVERIFIED` when labelled (ЕИК/БУЛСТАТ/EIK/BULSTAT/ДДС/UIC) |
| IBAN | `BGkk` + 4-letter bank code + 6 digits (branch, account type) + 8 alphanumerics (22) | ISO 13616 MOD-97 | `IBAN_BG` (strict shape and MOD-97); anything else of the looser shape `BGkk` + 4 letters + 14 alphanumerics, any case (a mistyped branch digit, a bad checksum, lower case) is `IBAN_BG_UNVERIFIED` |
| ID card (лична карта) | 9 digits (cards before 17 June 2024) or 2 letters + 7 digits (current card) | No public checksum | `BG_ID_CARD`, only after a context word (лична карта, л.к., ЛК, ID card, документ за самоличност) |
| Phone | `+359`/`00359`, mobile 87/88/89/98/99, Sofia 2, other area codes; national `0…` | Format | `PHONE_BG`; without the trunk 0 only after тел./GSM/мобилен |

## EGN over-masking (accepted, fail closed)

Under `bg-BG`, any unseparated 10-digit number whose digits read as a
plausible birth date (`YY` + month 01-12 or 41-52 + day 01-31) is masked
as `EGN_UNVERIFIED` even without a label. Known casualties:

- unspaced phone numbers such as `0301234567` (spaced forms like
  `030 12345678` or `+49 30 1234567` stay `PHONE_NUMBER`);
- Unix timestamps such as `1701151234`;
- order or reference numbers such as `Bestellnummer 8503154561`.

The value is restored in the response, so the cost is that the model
sees a placeholder instead of the number. Dates written as `15.03.2024`
(`DATE_DE`) or `2024-03-15` are not affected.

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
