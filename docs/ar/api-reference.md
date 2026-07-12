> translated from en/api-reference.md

# مرجع واجهة برمجة التطبيقات (API Reference)

مواصفات OpenAPI الكاملة متاحة في `docs/openapi.json` (يتم إنشاؤها تلقائيًا من تطبيق FastAPI). توفر هذه الصفحة ملخصًا لنقاط النهاية المتاحة.

## نقاط النهاية (Endpoints)

| الطريقة | المسار | الوصف |
|--------|------|-------------|
| POST | `/v1/chat/completions` | إرسال طلب دردشة (متوافق مع OpenAI) |
| GET | `/health` | فحص الصحة الإجمالي لجميع التبعيات |
| GET | `/v1/models` | سرد الأسماء المستعارة المتاحة للموديلات |
| GET | `/v1/compliance/presets` | سرد presets الخاصة بالامتثال المتاحة |
| GET | `/v1/config/rules` | سرد قواعد الكشف المخصصة النشطة |
| GET | `/metrics` | نقطة نهاية مقاييس Prometheus |

### POST /v1/chat/completions

يقبل نص طلب دردشة متوافق مع OpenAI. يدعم كلا الوضعين: البث (`stream: true`) وغير البث. راجع مواصفات OpenAPI للمخطط الكامل.

### GET /health

يعيد حالة الصحة الإجمالية للبوابة وتبعياتها (Presidio Analyzer و Valkey). الاستجابة:

```json
{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}
```

### GET /v1/models

يعيد قائمة الأسماء المستعارة للموديلات المهيأة وموفري الخدمة المستهدفين.

### GET /v1/compliance/presets

يعيد presets الخاصة بالامتثال المتاحة مع أنواع الكيانات المفروضة وعتبات الثقة الخاصة بها.

### GET /v1/config/rules

يعيد قواعد الكشف المخصصة النشطة (التعرفات وقوائم الاستبعاد).

### GET /metrics

يعيد المقاييس بتنسيق Prometheus بما في ذلك عدد الطلبات وزمن انتقال الكشف وعدد الكيانات وعدادات أحداث الأمان (fail-secure).

## المصادقة

تتطلب جميع نقاط نهاية واجهة برمجة التطبيقات (باستثناء `/health` و `/metrics`) رمز حامل (Bearer token) في ترويسة `Authorization`:

```bash
Authorization: Bearer <رمز-api-الخاص-بك>
```

يتم تكوين مفتاح API عبر متغير البيئة `ANONREQ_API_KEY`.

---
*هذه الوثيقة هي ترجمة للأصل الإنجليزي. في حالة وجود أي اختلاف، تسود النسخة الإنجليزية.*
