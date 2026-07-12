> translated from en/deployment.md

# النشر

## اعتبارات الإنتاج

### تخصيص الموارد

تأكد من أن المضيف لديك يلبي الحد الأدنى من متطلبات الموارد لجميع الحاويات الثلاث. بالنسبة لنشر الإنتاج، أضف هامشًا بنسبة 50% فوق ذروة الاستخدام المرصودة.

### تكوين السجلات

يتم كتابة السجلات في المخرجات القياسية بتنسيق JSON الهيكلي. قم بتكوين تجميع السجلات عبر أداتك المفضلة (برنامج تشغيل سجل Docker، أو syslog، أو ناقل سجلات مثل Fluentd أو Vector).

### أمن الشبكة

ترتبط البوابة بالمنفذ 8000. يتم عزل Presidio Analyzer و Valkey على شبكة Docker داخلية ولا يمكن الوصول إليهما مباشرة من الخارج.

### إنهاء TLS

قم بإنهاء TLS عند الوكيل العكسي (nginx أو Caddy أو موازن التحميل السحابي) وقم بالتوجيه إلى البوابة عبر HTTP على الشبكة الداخلية.

## متغيرات البيئة

| المتغير | النوع | الافتراضي | مطلوب | الوصف |
|----------|------|---------|----------|-------------|
| `ANONREQ_API_KEY` | string | — | نعم | رمز مصادقة API (أكبر من أو يساوي 32 حرفًا) |
| `ANONREQ_LOG_LEVEL` | string | `INFO` | لا | مستوى السجلات: DEBUG, INFO, WARNING, ERROR |
| `ANONREQ_CACHE_URL` | string | `valkey://localhost:6379` | لا | عنوان URL الخاص بخادم Valkey |
| `ANONREQ_CACHE_PASSWORD` | string | — | لا | كلمة مرور Valkey المطلوبة |
| `ANONREQ_CACHE_TTL` | int | `600` | لا | صلاحية الجلسة بالثواني (60-3600) |
| `ANONREQ_OPENAI_API_KEY` | string | — | مشروط | مفتاح API الخاص بـ OpenAI |
| `ANONREQ_ANTHROPIC_API_KEY` | string | — | مشروط | مفتاح API الخاص بـ Anthropic |
| `ANONREQ_GEMINI_API_KEY` | string | — | مشروط | مفتاح API الخاص بـ Google Gemini |
| `ANONREQ_OLLAMA_BASE_URL` | string | — | لا | عنوان URL لخادم Ollama |
| `ANONREQ_LOCALE` | string | `en-US` | لا | الإعداد الإقليمي الافتراضي للكشف |
| `ANONREQ_COMPLIANCE_PRESET` | string | — | لا | اسم preset الامتثال |
| `ANONREQ_CONFIDENCE_THRESHOLD` | float | `0.7` | لا | عتبة الثقة للكشف (0.0-1.0) |
| `PRESIDIO_ANALYZER_URL` | string | `http://presidio-analyzer:5001` | لا | عنوان URL الخاص بـ Presidio Analyzer |

## تكوين الإنتاج لـ Docker Compose

قم بتخصيص ملف `docker-compose.yml` الافتراضي باستخدام ملف `docker-compose.override.yml`:

```yaml
services:
  anonreq:
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "4G"
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
```

### تكوين فحص الصحة

تتضمن كل خدمة فحص صحة مدمج. راقب الخدمات الثلاث عبر نقطة نهاية البوابة `/health`. قم بإعداد مراقبة خارجية للتنبيه عند حدوث استجابات غير 200.

### سياسات إعادة التشغيل

تستخدم جميع الخدمات `restart: unless-stopped`. بالنسبة للنشر الخالي من فترات التوقف، قم بتشغيل نسخ متعددة للبوابة خلف موازن تحميل.

## السجلات

يتم إصدار سجلات JSON الهيكلية في المخرجات القياسية. الحقول الرئيسية: `timestamp` و `level` و `event` و `session_id` و `latency_ms` و `entity_count` و `provider`. استهلكها باستخدام أداة تجميع السجلات المفضلة لديك.

## الترقية

1. اسحب أحدث صورة: `docker compose pull anonreq`
2. أعد إنشاء الخدمات: `docker compose up -d --force-recreate anonreq`
3. تحقق من الصحة: `curl http://localhost:8000/health`

## الأمان

- تفشل البوابة بأمان (fail-secure): أي خطأ في الكشف أو التخزين المؤقت يعود بـ HTTP 5xx ولا يوجه أبدًا أي بيانات غير مطهرة إلى الموفرين الخارجيين
- تدوير مفاتيح API مدعوم عبر إعادة التشغيل: قم بتحديث `ANONREQ_API_KEY` في ملف `.env` وقم بتشغيل `docker compose restart anonreq`
- جميع بيانات ذاكرة التخزين المؤقت مؤقتة — لا يتم كتابة أي بيانات على القرص

---
*هذه الوثيقة هي ترجمة للأصل الإنجليزي. في حالة وجود أي اختلاف، تسود النسخة الإنجليزية.*
