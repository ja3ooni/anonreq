# Bulgarian (bg) strings — native review

Every Bulgarian string in `bg.json` is machine-assisted and **not final**.
Reviewer: **Ibtisam** (native speaker). Change a row's status to `approved (Ibtisam)` or
`changed (Ibtisam)` after review, and edit `bg.json` with the corrected text.
`src/lib/i18n-bg.test.ts` fails if a bg key is missing from this table.

Synthetic demo prompts in `src/lib/bg-demo-prompts.ts` are also pending review (listed at the end).

| Key | Bulgarian | English source | Status |
|---|---|---|---|
| `meta.title` | AnonReq | AnonReq | pending native review (Ibtisam) |
| `meta.description` | Вижте как една заявка се анонимизира, изпраща се към езиков модел и се възстановява. | Watch a prompt get anonymized, sent to xAI Grok, and restored. | pending native review (Ibtisam) |
| `nav.primary` | Основна навигация | Primary | pending native review (Ibtisam) |
| `nav.playground` | Демонстрация | Playground | pending native review (Ibtisam) |
| `nav.audit` | Одит | Audit | pending native review (Ibtisam) |
| `nav.skip` | Към съдържанието | Skip to content | pending native review (Ibtisam) |
| `nav.language` | Език | Language | pending native review (Ibtisam) |
| `nav.staff` | Чат за служители | Staff chat | pending native review (Ibtisam) |
| `status.mock` | Демо режим | Mock | pending native review (Ibtisam) |
| `status.live` | Шлюз | Gateway | pending native review (Ibtisam) |
| `status.down` | Шлюзът е недостъпен | Gateway unreachable | pending native review (Ibtisam) |
| `status.unconfigured` | Липсва ключ за шлюза | Gateway key missing | pending native review (Ibtisam) |
| `status.loading` | Проверка на шлюза | Checking gateway | pending native review (Ibtisam) |
| `footer.note` | Ключовете за доставчика остават на сървъра. Съответствията на маркерите не се пазят в този браузър. | Provider keys stay on the server. Token mappings are not stored in this browser. | pending native review (Ibtisam) |
| `common.missing` | — | — | pending native review (Ibtisam) |
| `playground.eyebrow` | xAI Grok през шлюза | xAI Grok through the gateway | pending native review (Ibtisam) |
| `playground.title` | Три изгледа на една заявка | Three views of one request | pending native review (Ibtisam) |
| `playground.lede` | Оригиналната заявка, маскираният текст, който моделът трябва да види, и отговорът, след като AnonReq върне реалните стойности. | The raw prompt, the masked text the model should see, and the answer after AnonReq puts the real values back. | pending native review (Ibtisam) |
| `playground.prompt` | Заявка | Prompt | pending native review (Ibtisam) |
| `playground.model` | Псевдоним на модела | Model alias | pending native review (Ibtisam) |
| `playground.modelHelp` | Изпраща се в полето model. Шлюзът разпознава псевдонима и извиква доставчика. | Sent as the model field. The gateway resolves the alias, then calls xAI. | pending native review (Ibtisam) |
| `playground.pinnedTenant` | Клиент (tenant) | Tenant | pending native review (Ibtisam) |
| `playground.pinnedTenantHelp` | Фиксиран на сървъра като ANONREQ_TENANT_ID. Тази страница не може да го промени. | Pinned on the server as ANONREQ_TENANT_ID. This page cannot change it. | pending native review (Ibtisam) |
| `playground.locale` | Език за разпознаване | Detection locale | pending native review (Ibtisam) |
| `playground.localeHelp` | Изпраща се като X-AnonReq-Locale. Не зависи от езика на страницата. | Sent as X-AnonReq-Locale. Separate from this page’s language. | pending native review (Ibtisam) |
| `playground.send` | Изпълни | Run | pending native review (Ibtisam) |
| `playground.sending` | Изпълнява се | Running | pending native review (Ibtisam) |
| `playground.done` | Резултатът е готов | Result is ready | pending native review (Ibtisam) |
| `playground.shortcut` | Ctrl или ⌘ и Enter за изпълнение | Ctrl or ⌘ and Enter to run | pending native review (Ibtisam) |
| `playground.samplePii` | Пример с лични данни | Sample with personal data | pending native review (Ibtisam) |
| `playground.sampleClean` | Пример без лични данни | Sample without personal data | pending native review (Ibtisam) |
| `playground.rawTitle` | Оригинална заявка | Raw prompt | pending native review (Ibtisam) |
| `playground.rawHint` | Това, което изпратихте. Откритите данни се маркират, когато отговори крайната точка за преглед. | What you sent. Spans are marked when the preview endpoint answers. | pending native review (Ibtisam) |
| `playground.anonTitle` | Анонимизирана заявка | Anonymized prompt | pending native review (Ibtisam) |
| `playground.anonHint` | Това, което напуска мрежата: маркери [TYPE_N] вместо лични данни. | What leaves the network: [TYPE_N] tokens instead of personal data. | pending native review (Ibtisam) |
| `playground.modelRawTitle` | Отговор на модела (преди възстановяване) | Model reply (before restore) | pending native review (Ibtisam) |
| `playground.modelRawHint` | Реалният отговор на модела — все още с маркери [TYPE_N], преди AnonReq да ги възстанови. | Actual response from Grok over the wire — still using [TYPE_N] tokens before AnonReq restores them. | pending native review (Ibtisam) |
| `playground.answerTitle` | Отговор с възстановени данни | Re-identified answer | pending native review (Ibtisam) |
| `playground.answerHint` | Отговорът на модела, след като AnonReq възстанови обратимите маркери. | The model reply after AnonReq restores reversible tokens. | pending native review (Ibtisam) |
| `playground.empty` | Изпълнете заявка, за да се попълнят колоните. | Run a prompt to fill these columns. | pending native review (Ibtisam) |
| `playground.previewDisabledTitle` | Анонимизираната заявка липсва в отговора на API | Anonymized prompt is not in the API response | pending native review (Ibtisam) |
| `playground.previewDisabledBody` | POST /v1/chat/completions връща възстановения отговор и заглавките X-AnonReq-*, но не и маскираната заявка. Тази колона се попълва, когато POST /v1/debug/anonymize-preview е включен (ANONREQ_DEBUG_PREVIEW_ENABLED=true и администраторски ключ). Код 404 означава, че настройката е изключена. Прегледът не извиква модела. | POST /v1/chat/completions returns the restored answer and the X-AnonReq-* headers. It does not return the masked prompt. This column fills when POST /v1/debug/anonymize-preview is enabled (ANONREQ_DEBUG_PREVIEW_ENABLED=true and an admin credential). A 404 means that flag is off. The preview does not call the model. | pending native review (Ibtisam) |
| `playground.previewError` | Прегледът не успя | Preview failed | pending native review (Ibtisam) |
| `playground.rateLimited` | Достигнат е лимитът за прегледи на този администратор. Изчакайте малко и опитайте отново. | This admin has hit the preview rate limit. Wait a moment, then run the prompt again. | pending native review (Ibtisam) |
| `playground.noEntities` | В прегледа няма открити данни. | No entities in the preview. | pending native review (Ibtisam) |
| `playground.previewRequestId` | Идентификатор на заявката за преглед | Preview request id | pending native review (Ibtisam) |
| `playground.separateCalls` | Прегледът и отговорът са отделни заявки, всяка със свой идентификатор. | Preview and completion are separate calls, each with its own request id. | pending native review (Ibtisam) |
| `playground.headersTitle` | Заглавки на отговора | Completion response headers | pending native review (Ibtisam) |
| `playground.headersEmpty` | Заглавките се показват след отговор. | Headers appear after a completion. | pending native review (Ibtisam) |
| `playground.legend` | Видове данни | Entity types | pending native review (Ibtisam) |
| `playground.chatError` | Отговорът не успя | Completion failed | pending native review (Ibtisam) |
| `playground.network` | Демо интерфейсът не успя да се свърже със собствения си сървър. | The demo UI could not reach its own server route. | pending native review (Ibtisam) |
| `playground.spansMissing` | Маркировките се показват, когато крайната точка за преглед е налична. | Entity marks appear when the preview endpoint is available. | pending native review (Ibtisam) |
| `playground.scanOnly` | Само проверка — може ли? | Scan Only — Is It OK? | pending native review (Ibtisam) |
| `playground.scanning` | Проверява се… | Scanning… | pending native review (Ibtisam) |
| `playground.sendWithGrok` | Анонимизирай и попитай Grok | Anonymize & Ask Grok | pending native review (Ibtisam) |
| `playground.scenariosTitle` | Примерни сценарии (ЕС) | Frankfurt EU Buyer Scenarios | pending native review (Ibtisam) |
| `playground.scenariosHint` | Изберете сценарий от регулиран сектор или качете свой файл по-долу | Pick a regulated industry case or upload your own file below | pending native review (Ibtisam) |
| `playground.personaLabel` | Целева роля | Buyer Persona | pending native review (Ibtisam) |
| `playground.painLabel` | Проблем със съответствието | Compliance Pain | pending native review (Ibtisam) |
| `playground.valueLabel` | Гаранция от AnonReq | AnonReq Guarantee | pending native review (Ibtisam) |
| `playground.buyerLineLabel` | Основно послание | Pitch Line | pending native review (Ibtisam) |
| `playground.downloadSample` | Изтеглете примерен файл за тест на качването: | Download sample file to test upload: | pending native review (Ibtisam) |
| `playground.uploadTitle` | Проверка и качване на файл (.pdf, .docx, .txt, .csv, .json, .md, .log, .eml) | File Readiness Check & Upload (.pdf, .docx, .txt, .csv, .json, .md, .log, .eml) | pending native review (Ibtisam) |
| `playground.uploadDrop` | Пуснете документ тук или щракнете, за да изберете | Drop a document here or click to browse | pending native review (Ibtisam) |
| `playground.uploadSub` | Текстът се извлича локално на демо сървъра и се проверява дали е безопасно да се изпрати към ИИ. | Extracts text locally on the demo server and checks whether it is safe to send to AI. | pending native review (Ibtisam) |
| `playground.uploading` | Извличане на текста от файла… | Extracting text from file… | pending native review (Ibtisam) |
| `playground.uploadedBadge` | Зареден файл | Loaded file | pending native review (Ibtisam) |
| `playground.clearFile` | Премахни файла | Clear file | pending native review (Ibtisam) |
| `playground.taskLabel` | Задача или инструкция за ИИ (по избор, при изпращане към Grok) | Optional AI Task / Instruction (when sending to Grok) | pending native review (Ibtisam) |
| `playground.verdictHeading` | Решение на шлюза — може ли този файл или заявка? | AI Gate Verdict — Is This File / Prompt OK? | pending native review (Ibtisam) |
| `playground.verdictCleanTitle` | Може да се изпрати — няма регулирани идентификатори | OK to Send — No Regulated Identifiers Detected | pending native review (Ibtisam) |
| `playground.verdictCleanBody` | Не са открити лични идентификатори или пароли. Класификация: PUBLIC. | 0 personal identifiers or credentials were found. Classification is PUBLIC. | pending native review (Ibtisam) |
| `playground.verdictGovernedTitle` | Не като открит текст → безопасно през шлюза AnonReq | Not OK in Cleartext → SAFE via AnonReq Gateway | pending native review (Ibtisam) |
| `playground.verdictGovernedBody` | Директно качване в ChatGPT/Grok би разкрило {count} регулирани фрагмента ({classification}). AnonReq заменя всеки идентификатор с обратим маркер преди изпращане. | Direct upload to ChatGPT/Grok would expose {count} regulated spans ({classification}). AnonReq replaces every identifier with a reversible token before outbound transit. | pending native review (Ibtisam) |
| `playground.verdictSecretTitle` | Открити критични идентификационни данни → трайно премахнати | Critical Credential Detected → Permanently Redacted | pending native review (Ibtisam) |
| `playground.verdictSecretBody` | Открити са {secretCount} необратими идентификационни данни (API_KEY) сред общо {total} фрагмента. AnonReq маскира тайните трайно (никога не се възстановяват в отговора), а разрешените лични данни се възстановяват. | Found {secretCount} non-reversible credential(s) (API_KEY) alongside {total} total spans. AnonReq masks secrets permanently (never restored in the model reply) while restoring authorized PII. | pending native review (Ibtisam) |
| `playground.verdictFailClosedTitle` | Защитно блокиране — 0 байта към модела | Fail-Closed Active — 0 Bytes Forwarded to Upstream LLM | pending native review (Ibtisam) |
| `playground.verdictFailClosedBody` | Услугата за разпознаване е недостъпна или отхвърли езика. AnonReq блокира заявката, вместо да рискува изтичане на открит текст. | Detection sidecar is unreachable or rejected the locale. AnonReq blocked the request rather than risking a cleartext leak. | pending native review (Ibtisam) |
| `playground.cleartextStatus` | Директно към облачен модел | Direct to Cloud LLM | pending native review (Ibtisam) |
| `playground.cleartextUnsafe` | БЛОКИРАНО (риск от изтичане на лични данни) | BLOCKED (PII Leak Risk) | pending native review (Ibtisam) |
| `playground.cleartextSafe` | БЕЗОПАСНО (0 лични данни) | SAFE (0 PII) | pending native review (Ibtisam) |
| `playground.gatewayStatus` | През шлюза AnonReq | Via AnonReq Gateway | pending native review (Ibtisam) |
| `playground.gatewaySafe` | КОНТРОЛИРАНО И БЕЗОПАСНО | GOVERNED & SAFE | pending native review (Ibtisam) |
| `playground.gatewayBlocked` | ЗАЩИТНО БЛОКИРАНЕ (5xx) | FAIL-CLOSED (5xx) | pending native review (Ibtisam) |
| `playground.downloadSanitized` | Изтегли изчистения текст (.txt) | Download Sanitized (.txt) | pending native review (Ibtisam) |
| `playground.copySanitized` | Копирай маскирания текст | Copy Masked Text | pending native review (Ibtisam) |
| `playground.copied` | Копирано! | Copied! | pending native review (Ibtisam) |
| `playground.reversibleBadge` | Обратимо | Reversible | pending native review (Ibtisam) |
| `playground.nonReversibleBadge` | Трайно маскирано | Permanent Mask | pending native review (Ibtisam) |
| `playground.sessionRequests` | Проверки / изпълнения | Scans / Runs | pending native review (Ibtisam) |
| `playground.sessionEntities` | Маскирани елементи | Entities Masked | pending native review (Ibtisam) |
| `playground.sessionSecrets` | Блокирани тайни | Secrets Blocked | pending native review (Ibtisam) |
| `playground.exportDpoCsv` | Изтегли одитен CSV за ДЗЛД | Export DPO Audit CSV | pending native review (Ibtisam) |
| `playground.sponsorDrawerTitle` | GlassFlow (Rius + Tares) · Пилотен проект · 90-секундно демо | GlassFlow (Rius + Tares) · Pilot PoC · 90s Demo Guide | pending native review (Ibtisam) |
| `playground.tabGlassflow` | GlassFlow Rius и Tares | GlassFlow Rius & Tares | pending native review (Ibtisam) |
| `playground.tabPilot` | Пилотен проект | Frankfurt Pilot PoC | pending native review (Ibtisam) |
| `playground.tabScript` | Сценарий за 90 секунди | 90s Demo Script | pending native review (Ibtisam) |
| `samples.pii` | [СИНТЕТИЧНИ ДАННИ] Подготви кратък отговор до Иван Тестов Примеров (ivan.testov@example.org, +359 88 000 0001), ЕГН 9999999999. Сметката е BG78 TEST 0000 1234 5678 90. Ще бъде в София на 14.03.2026. | Draft a short reply to Jörg Müller (joerg.mueller@nordbank.example, +49 170 1234567). The IBAN is DE89 3704 0044 0532 0130 00. He will be in München on 14.03.2026. | pending native review (Ibtisam) |
| `samples.clean` | Обясни с три изречения как шлюз, който блокира при грешка, се различава от прокси. | Explain in three sentences how a gateway that blocks on failure differs from a proxy. | pending native review (Ibtisam) |
| `headers.requestId` | X-AnonReq-Request-ID | X-AnonReq-Request-ID | pending native review (Ibtisam) |
| `headers.entityCount` | X-AnonReq-Entity-Count | X-AnonReq-Entity-Count | pending native review (Ibtisam) |
| `headers.classification` | X-AnonReq-Classification | X-AnonReq-Classification | pending native review (Ibtisam) |
| `headers.highestEntity` | X-AnonReq-Highest-Entity | X-AnonReq-Highest-Entity | pending native review (Ibtisam) |
| `headers.processed` | X-AnonReq-Processed | X-AnonReq-Processed | pending native review (Ibtisam) |
| `audit.eyebrow` | Само метаданни | Metadata only | pending native review (Ibtisam) |
| `audit.title` | Одитен журнал | Audit log | pending native review (Ibtisam) |
| `audit.lede` | Кой потребител кой модел е извикал и какви видове данни са маскирани. Реални стойности няма в журнала. | Who called which model, and which entity types were masked. Raw values are not in this log. | pending native review (Ibtisam) |
| `audit.filters` | Филтри | Filters | pending native review (Ibtisam) |
| `audit.from` | От | From | pending native review (Ibtisam) |
| `audit.to` | До | To | pending native review (Ibtisam) |
| `audit.entity` | Вид данни | Entity type | pending native review (Ibtisam) |
| `audit.entityPlaceholder` | Всички | Any | pending native review (Ibtisam) |
| `audit.tenant` | Клиент (tenant) | Tenant | pending native review (Ibtisam) |
| `audit.tenantPlaceholder` | Всички | Any | pending native review (Ibtisam) |
| `audit.sort` | Подредба | Sort | pending native review (Ibtisam) |
| `audit.newest` | Първо най-новите | Newest first | pending native review (Ibtisam) |
| `audit.oldest` | Първо най-старите | Oldest first | pending native review (Ibtisam) |
| `audit.limit` | Редове на страница | Page size | pending native review (Ibtisam) |
| `audit.apply` | Приложи | Apply | pending native review (Ibtisam) |
| `audit.reset` | Изчисти | Reset | pending native review (Ibtisam) |
| `audit.export` | Изтегли CSV | Export CSV | pending native review (Ibtisam) |
| `audit.exporting` | Изтегля се | Exporting | pending native review (Ibtisam) |
| `audit.fallback` | Липсва одитният API с курсор (404). Таблицата в демото е извадка от стария експорт на анонимизации, който няма курсор и отделен общ брой. Старият CSV е файлът на шлюза, не тази страница. | The cursor audit API is missing (404). This table is sliced in the demo from the legacy anonymization export, which has no cursor and no separate total. The legacy CSV is the gateway file, not this page. | pending native review (Ibtisam) |
| `audit.loadMore` | Зареди още | Load more | pending native review (Ibtisam) |
| `audit.tenantForbidden` | Този клиент не е клиентът на заявителя. Шлюзът отказа достъп до одита. | That tenant is not the caller’s tenant. The gateway refused the audit read. | pending native review (Ibtisam) |
| `audit.exportPartial` | Експортът спря по средата. Изтегленият файл не съдържа неуспешната част и може да е непълен. | The export stopped partway. The downloaded file omits the failed tail and may be incomplete. | pending native review (Ibtisam) |
| `audit.loadingMore` | Зареждат се още | Loading more | pending native review (Ibtisam) |
| `audit.loaded` | {count} от {total} | {count} of {total} | pending native review (Ibtisam) |
| `audit.loadedInexact` | Заредени {count} от този експорт ({total} реда, без отделен общ брой) | {count} loaded from this export ({total} rows, no separate total) | pending native review (Ibtisam) |
| `audit.previous` | Назад | Previous | pending native review (Ibtisam) |
| `audit.next` | Напред | Next | pending native review (Ibtisam) |
| `audit.empty` | Няма събития по тези филтри. | No events match these filters. | pending native review (Ibtisam) |
| `audit.loading` | Зареждане на събитията | Loading events | pending native review (Ibtisam) |
| `audit.tableScroll` | Събития по анонимизация, превъртете хоризонтално за още колони | Anonymization events, scroll sideways for more columns | pending native review (Ibtisam) |
| `audit.caption` | Дейност по анонимизация | Anonymization activity | pending native review (Ibtisam) |
| `audit.time` | Час | Time | pending native review (Ibtisam) |
| `audit.request` | Заявка | Request | pending native review (Ibtisam) |
| `audit.model` | Модел | Model | pending native review (Ibtisam) |
| `audit.locale` | Език | Locale | pending native review (Ibtisam) |
| `audit.entities` | Видове данни | Entities | pending native review (Ibtisam) |
| `audit.tokens` | Маркери | Tokens | pending native review (Ibtisam) |
| `audit.decision` | Решение | Decision | pending native review (Ibtisam) |
| `audit.verifyTitle` | Хеш верига | Hash chain | pending native review (Ibtisam) |
| `audit.verifyAction` | Провери веригата | Verify chain | pending native review (Ibtisam) |
| `audit.verifyLoading` | Проверява се | Verifying | pending native review (Ibtisam) |
| `audit.intact` | Цяла | Intact | pending native review (Ibtisam) |
| `audit.broken` | Прекъсната | Broken | pending native review (Ibtisam) |
| `audit.checked` | Проверени събития: {count} | {count} events checked | pending native review (Ibtisam) |
| `audit.brokenAt` | Прекъсната при {id} | Broken at {id} | pending native review (Ibtisam) |
| `audit.tabsActivity` | Анонимизация | Anonymization | pending native review (Ibtisam) |
| `audit.tabsConfig` | История на настройките | Config history | pending native review (Ibtisam) |
| `audit.configFilters` | Филтри за историята на настройките | Config history filters | pending native review (Ibtisam) |
| `audit.changeType` | Вид промяна | Change type | pending native review (Ibtisam) |
| `audit.operator` | Оператор | Operator | pending native review (Ibtisam) |
| `audit.configCaption` | Промени в настройките | Configuration changes | pending native review (Ibtisam) |
| `audit.event` | Събитие | Event | pending native review (Ibtisam) |
| `audit.change` | Промяна | Change | pending native review (Ibtisam) |
| `audit.prevHash` | Предишен хеш | Previous hash | pending native review (Ibtisam) |
| `audit.newHash` | Нов хеш | New hash | pending native review (Ibtisam) |
| `audit.configEmpty` | Няма промени в настройките по тези филтри. | No config changes match these filters. | pending native review (Ibtisam) |
| `audit.exportLoaded` | Изтегли заредените редове | Export loaded rows | pending native review (Ibtisam) |
| `audit.configLoading` | Зареждане на историята на настройките | Loading config history | pending native review (Ibtisam) |
| `audit.exportError` | Изтеглянето на CSV не успя | CSV export failed | pending native review (Ibtisam) |
| `notice.assistive` | Само за помощ — човек трябва да прегледа отговора | Assistive only — a human must review | pending native review (Ibtisam) |
| `notice.detail` | Отговорите на ИИ може да са грешни. Проверете всеки отговор, преди да стигне до гражданин или да послужи за решение. | AI replies can be wrong. Check every reply before it reaches a citizen or informs a decision. | pending native review (Ibtisam) |
| `notice.label` | Важно | Notice | pending native review (Ibtisam) |
| `staff.eyebrow` | Асистент за общински служители · пилотен проект | Municipal staff assistant · pilot | pending native review (Ibtisam) |
| `staff.title` | Попитайте асистента, личните данни остават при нас | Ask the assistant, keep personal data local | pending native review (Ibtisam) |
| `staff.lede` | Личните данни се заменят с маркери, преди заявката да напусне мрежата. Сравнете какво видя моделът с това, което виждате вие. | Personal data is replaced with tokens before the request leaves the network. Compare what the model saw with what you see. | pending native review (Ibtisam) |
| `staff.model` | Модел | Model | pending native review (Ibtisam) |
| `staff.modelHelp` | BgGPT е първи в списъка. Шлюзът разпознава псевдонима. | BgGPT is listed first. The gateway resolves the alias. | pending native review (Ibtisam) |
| `staff.bggptPending` | Псевдонимът на BgGPT още не е потвърден (временно: {alias}) | BgGPT alias not confirmed yet (placeholder: {alias}) | pending native review (Ibtisam) |
| `staff.examples` | Примерни заявки | Example requests | pending native review (Ibtisam) |
| `staff.examplesHint` | Само синтетични данни. Без реални лица, ЕГН или IBAN. | Synthetic data only. No real person, EGN or IBAN. | pending native review (Ibtisam) |
| `staff.syntheticBadge` | Синтетични | Synthetic | pending native review (Ibtisam) |
| `staff.prompt` | Вашата заявка | Your request | pending native review (Ibtisam) |
| `staff.send` | Изпрати | Send | pending native review (Ibtisam) |
| `staff.sending` | Изпраща се… | Sending… | pending native review (Ibtisam) |
| `staff.done` | Отговорът е готов | Reply is ready | pending native review (Ibtisam) |
| `staff.modelSawTitle` | Какво видя моделът | What the model saw | pending native review (Ibtisam) |
| `staff.modelSawHint` | Маркери вместо лични данни. Само това напусна мрежата. | Tokens instead of personal data. This is all that left the network. | pending native review (Ibtisam) |
| `staff.youSeeTitle` | Какво виждате вие | What you see | pending native review (Ibtisam) |
| `staff.youSeeHint` | Вашата заявка и отговорът с възстановени реални стойности. | Your request and the reply with the real values restored. | pending native review (Ibtisam) |
| `staff.requestLabel` | Заявка | Request | pending native review (Ibtisam) |
| `staff.replyLabel` | Отговор | Reply | pending native review (Ibtisam) |
| `staff.empty` | Изпратете заявка, за да се попълнят двата изгледа. | Send a request to fill both views. | pending native review (Ibtisam) |
| `staff.maskedCount` | Маскирани елементи: {count} | {count} items masked | pending native review (Ibtisam) |
| `staff.previewDisabled` | Маскираната заявка не е налична. Крайната точка за преглед е изключена (ANONREQ_DEBUG_PREVIEW_ENABLED). | The masked request is not available. The preview endpoint is off (ANONREQ_DEBUG_PREVIEW_ENABLED). | pending native review (Ibtisam) |
| `staff.previewError` | Прегледът на маскирането не успя | Masking preview failed | pending native review (Ibtisam) |
| `staff.chatError` | Асистентът не отговори | The assistant did not reply | pending native review (Ibtisam) |
| `staff.network` | Страницата не успя да се свърже със сървъра си. | This page could not reach its server. | pending native review (Ibtisam) |
| `staff.adminTitle` | Администрация | Administration | pending native review (Ibtisam) |
| `staff.exportCsv` | Изтегли одитен CSV | Export audit CSV | pending native review (Ibtisam) |
| `staff.exportHint` | Само метаданни: видове и брой елементи, никога реални стойности. | Metadata only: entity types and counts, never raw values. | pending native review (Ibtisam) |
| `staff.openAudit` | Отвори одитния журнал | Open audit log | pending native review (Ibtisam) |
| `staff.detectionLocale` | Език за разпознаване: {locale} | Detection locale: {locale} | pending native review (Ibtisam) |
| `bg-demo-prompts:social-assistance` | see `src/lib/bg-demo-prompts.ts` | — | pending native review (Ibtisam) |
| `bg-demo-prompts:address-registration` | see `src/lib/bg-demo-prompts.ts` | — | pending native review (Ibtisam) |
| `bg-demo-prompts:no-personal-data` | see `src/lib/bg-demo-prompts.ts` | — | pending native review (Ibtisam) |
