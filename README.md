# 📷 camdetect v1.0 — بديل عملي سريع لـ clearcam

> نفس الفكرة (كشف + تتبع + تنبيهات + بحث لأي كاميرا) لكن **أخف وأسرع وأسهل تشغيلاً**: بدون ffmpeg، بدون tinygrad، يعمل فوراً على Windows/Mac/Linux.

## لماذا أسرع من clearcam؟
| clearcam | camdetect |
|---|---|
| tinygrad + YOLOv9 ثقيل + تجميع أول تشغيل | HOG فوري + YOLOv8n اختياري فقط |
| ffmpeg HLS لكل كاميرا (CPU عالٍ) | MJPEG مباشر من OpenCV (بدون ffmpeg) |
| OC-SORT Kalman ثقيل | Centroid tracker خفيف (500+ FPS) |
| يستدل كل فريم | **motion gate + frame_skip**: يتخطى الفريمات الساكنة (3-5x أسرع) |
| queue غير محدودة = تأخير | queue بحجم 1 (الأحدث فقط) = زمن استجابة ~0 |
| DB بدون prune | prune تلقائي + WAL |

## التشغيل (دقيقتان)
```bat
cd camdetect
pip install -r requirements.txt
python -m camdetect
```
افتح: http://127.0.0.1:8080

للدقة الأعلى (اختياري): `pip install ultralytics` — سيُستخدم YOLOv8n تلقائياً، وإلا يعمل HOG/Motion فوراً بدون إنترنت.

## إضافة كاميرا
- ويب كام: `0` أو `1`
- كاميرا مراقبة: `rtsp://user:pass@192.168.1.10:554/stream`
- ملف/رابط: `C:/vid.mp4` أو `https://.../stream.m3u8`
- من الواجهة: ➕ إضافة كاميرا

## المزايا المتكاملة
- 🔴 بث مباشر MJPEG متعدد الكاميرات + FPS/ms لكل كاميرا
- 🧠 كشف: person/car/cat/dog/... (YOLO) أو person (HOG) أو motion — تلقائي
- 🧭 تتبع + عد + معرف track ثابت
- 🗺️ مناطق include/exclude بالرسم على لقطة
- 🔎 بحث: نص/فئة/تاريخ/كاميرا + صور مصغرة
- 🔔 تنبيهات: webhook (Discord/Slack/Home-Assistant) + Telegram + cooldown ضد الإزعاج
- 🧹 تنظيف تلقائي + SQLite WAL سريع
- 🌐 واجهة عربية/إنجليزية RTL

## API
- `GET /api/health` `GET /api/cameras` `POST /api/cameras` `DELETE /api/cameras/<n>`
- `GET /stream/<n>` (MJPEG) `GET /snap/<n>` (JPEG)
- `GET /api/events?q=&label=&date=&cam=` `GET /api/thumb/<id>`
- `POST /api/zones/<n>` `GET/POST /api/config` `POST /api/notify_test`

## الإعدادات (config.json)
- `inference.engine: auto/yolo/hog/motion` • `imgsz: 480` (أصغر=أسرع) • `conf` • `frame_skip: 2` • `motion_gate: true`
- `alerts.cooldown_sec: 20` • `notify.webhook_url / telegram_*`

## ملاحظات عملية
- لا يحتاج GPU ولا ffmpeg. يعمل على أي لابتوب.
- RTSP عبر OpenCV مباشرة (TCP تلقائي). إن تعثر البث: قلل `imgsz` إلى 320 وزد `frame_skip` إلى 3.
- الكاميرات تُحفظ في `config.json`، الأحداث في `data/camdetect.db`، الصور في `data/thumbs/`.
