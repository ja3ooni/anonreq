> translated from en/installation.md

# التثبيت

## المتطلبات الأساسية

- Python 3.12+
- Docker Engine 24+ مع Docker Compose v2+
- 4 جيجابايت رام كحد أدنى (يوصى بـ 8 جيجابايت)

## استنساخ المستودع

```bash
git clone https://github.com/anonreq/anonreq.git
cd anonreq
```

## تكوين البيئة

انسخ ملف البيئة النموذجي وقم بتكوين المتغيرات المطلوبة:

```bash
cp .env.example .env
```

| المتغير | مطلوب | الافتراضي | الوصف |
|----------|------|---------|-------------|
| `ANONREQ_API_KEY` | نعم | — | رمز حامل ثابت لمصادقة API (أكبر من أو يساوي 32 حرفًا) |
| `ANONREQ_LOG_LEVEL` | لا | `INFO` | مستوى تسجيل السجلات |
| `ANONREQ_CACHE_TTL` | لا | `600` | صلاحية ذاكرة التخزين المؤقت للجلسة بالثواني |
| `ANONREQ_PRESIDIO_URL` | لا | `http://presidio-analyzer:5001` | عنوان URL الخاص بـ Presidio Analyzer |
| `ANONREQ_VALKEY_URL` | لا | `valkey://localhost:6379` | سلسلة اتصال Valkey |

يجب تعيين مفتاح API الخاص بموفر خدمة واحد على الأقل (`ANONREQ_OPENAI_API_KEY` أو `ANONREQ_ANTHROPIC_API_KEY` أو `ANONREQ_GEMINI_API_KEY`).

## إعداد Docker Compose

```bash
docker compose up -d --wait
```

يؤدي هذا إلى تشغيل الخدمات الثلاث: `anonreq` (البوابة) و `presidio-analyzer` (الكشف عن PII) و `valkey` (ذاكرة التخزين المؤقت المؤقتة).

## التحقق من التثبيت

```bash
curl http://localhost:8000/health
```

الاستجابة المتوقعة: HTTP 200 مع `{"status":"pass","checks":{"presidio":"pass","valkey":"pass"}}`.

## استكشاف الأخطاء وإصلاحها

| المشكلة | السبب المرجح | الحل |
|----------|----------------|----------|
| اختبار الصحة يعود بـ 503 | نموذج Presidio لا يزال قيد التحميل | انتظر 60 ثانية لتنزيل النموذج، ثم أعد المحاولة |
| فشل `docker compose up` | المنفذ 8000 قيد الاستخدام | أوقف الخدمات الأخرى أو قم بتغيير تعيين المنافذ |
| `curl: connection refused` | البوابة ليست جاهزة | قم بتشغيل `docker compose ps` للتحقق من الحالة |

---
*هذه الوثيقة هي ترجمة للأصل الإنجليزي. في حالة وجود أي اختلاف، تسود النسخة الإنجليزية.*
