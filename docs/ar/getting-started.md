> translated from en/getting-started.md

# ابدأ الآن مع AnonReq

## المتطلبات الأساسية

- Docker Engine 24+
- Docker Compose v2+
- مفتاح API الخاص بـ OpenAI أو Anthropic أو Gemini

## التشغيل السريع

قم بتشغيل البرامج النصية التالية من جذر المستودع:

```bash
# الخطوة 1: بدء تشغيل البوابة
./examples/quickstart/01-start-gateway.sh

# الخطوة 2: إرسال طلب اختبار يحتوي على PII
./examples/quickstart/02-basic-anonymization.sh

# الخطوة 3: التنظيف
./examples/quickstart/03-cleanup.sh
```

تتعامل البرامج النصية للتشغيل السريع مع جميع عمليات الإعداد والتحقق والتنظيف تلقائيًا. ينتهي كل برنامج نصي بالرمز 0 عند النجاح أو 1 عند الفشل مع إخراج التشخيص.

## الخطوات التالية

- راجع `docs/en/installation.md` للحصول على إرشادات التثبيت التفصيلية
- راجع `examples/curl/` و `examples/python/` و `examples/typescript/` و `examples/go/` للحصول على أمثلة SDK بلغتك
- راجع `docs/en/deployment.md` للحصول على إرشادات النشر في بيئة الإنتاج
- راجع `docs/en/compliance.md` لتكوين presets الخاصة بالامتثال
- راجع ملف README الخاص بالمشروع للحصول على نظرة عامة كاملة

---
*هذه الوثيقة هي ترجمة للأصل الإنجليزي. في حالة وجود أي اختلاف، تسود النسخة الإنجليزية.*
