# UZEX Spot Data AI Agent — Solution Architecture & Technical Report

---

## 🇺🇿 O‘ZBEK TILI

### 1. Muammoning qo‘yilishi va talablar
O‘zbekiston respublika tovar-xom ashyo birjasining (UZEX) 2022–2026 yillardagi 500 000 ta bitimdan iborat ochiq reyestri asosida savollarga o‘zbek va rus tillarida qat’iy faktik javob beruvchi sun’iy intellekt agenti ishlab chiqildi.
- **Asosiy qoidalar**:
  - Javob tili = Savol tili.
  - O‘ylab topilgan raqam, tovar yoki korxona = Diskvalifikatsiya (0 ball).
  - Har bir javob 90 soniya ichida (maqsadli ko‘rsatkich < 15 s).
  - Ma’lumotlar bazasida javob bo‘lmasa — ochiq va asosli rad etish.
  - Har bir javob yakunida Asos (Evidence) bloki: talqin, ta’rif, SQL, qatorlar soni, namuna bitimlar.

### 2. Tizim arxitekturasi

```
[Foydalanuvchi / Web UI]
           │
           ▼
[FastAPI Server] (Rate limiting: 60 rpm, Sessiya xotirasi)
           │
           ▼
[Tilni aniqlash & Xavfsizlik filtri] (O'zbek/Rus, Prompt Injection tekshiruvi)
           │
           ▼
[Entitilarni kodda aniqlash (Entity Resolver)]
  ├── STIR (9 xona), Bitim ID, Broker kodi (BK001..BK120)
  ├── 40 ta TN VED tovar kodlari lug'ati (Sinonimlar & ildizlar)
  └── Tashqaridagi savollar filtri (Oltin, avto, rahbarlar, prognozlar)
           │
           ▼
[Deterministik SQL Rejalashtiruvchi] ──(Topilmasa)──► [LLM Fallback Chain]
  (15 ta asosiy savol turi bo'yicha)                   (Gemini 2.5 Flash / OpenAI)
           │                                                    │
           └──────────────────┬─────────────────────────────────┘
                              ▼
                     [SQL Guard (Xavfsizlik)]
                       ├── Faqat SELECT ruxsat etilgan
                       ├── Xavfli kalit so'zlar taqiqlangan
                       └── LIMIT 1000 majburiy
                              │
                              ▼
                [Normallashtirilgan SQLite DB (Read-Only)]
                (500k bitim, indekslangan, hisoblangan ustunlar)
                              │
                              ▼
               [Lokal Javob Rendereri (Renderer)]
               (Raqamlarni formatlash, O'zbek/Rus birliklari)
                              │
                              ▼
             [Faktik Asoslanganlik Tekshiruvi (Verifier)]
             (Har bir raqam DB qatorida borligini kafolatlaydi)
                              │
                              ▼
                [Asos (Evidence) bloki bilan Yakuniy Javob]
```

### 3. Ma’lumotlarni normallashtirish va hisoblangan ustunlar
- `volume` = `quantity * lot` (O‘lchov birligidagi aniq hajm).
- `unit_price` = `amount / volume` (Birlik narxi).
- `value_uzs` = Eksport bitimlari uchun `amount * usd_rate` (bitim sanasidagi kurs).
- `is_late` = `1`, agar yetkazib berish muddati buzilgan bo‘lsa (`delivery_date > payment_date + delivery_days`).
- `is_annulled` = `1`, bekor qilingan bitimlar (`Аннулирован(Не оплачен)` — 33 719 ta).
- `delivered_volume` = `delivered * lot` (Qisman yetkazilgan bitimlar uchun).

### 4. Hallyutsinatsiyaga qarshi mexanizm (Anti-Hallucination)
1. **Deterministik raqamlar**: Birorta ham raqam yoki korxona nomi LLM tomonidan to‘qilmaydi.
2. **Grounding Verifier**: Javob matnidagi har bir son va sana SQL natijasidagi qatorlar bilan taqqoslanadi. Agar bazada bo‘lmagan raqam aniqlansa, javob avtomatik ravishda xom ma’lumotlar jadvaliga almashtiriladi.
3. **Qamrovdan tashqari savollar**: Birjada sotilmaydigan tovarlar (oltin), rahbarlar ismi, telefonlar, 2027 yil prognozlari aniqlanganda darhol faktik tushuntirish bilan javob beriladi.

### 5. Sinov natijalari (Haqiqiy raqamlar)
- **Golden Suite (50 ta savol, 25 ta UZ, 25 ta RU, 12 ta tuzoq)**:
  - Muvaffaqiyatli o‘tdi: **50 / 50 (100.0%)**
  - O‘rtacha javob vaqti: **203.1 ms** (90 soniya limitidan 400 barobar tezroq!)
  - Maksimal javob vaqti: **1.45 s**
- **Oflayn birlik testlari (pytest)**: **10 / 10 passed (0.11 s)**.

---

## 🇷🇺 РУССКИЙ ЯЗЫК

### 1. Постановка задачи и требования
Разработан интеллектуальный агент для товарно-сырьевой биржи (UZEX), обеспечивающий строго фактологические ответы на русском и узбекском языках по открытому реестру из 500 000 сделок (2022–2026).
- **Ключевые регламенты**:
  - Язык ответа строго совпадает с языком вопроса.
  - Любое придуманное число, компания или товар — мгновенная дисквалификация.
  - Лимит времени: 90 секунд (фактически < 0.3 с).
  - Блок Evidence (Обоснование) в каждом ответе: SQL, фильтры, определение, количество строк, номера сделок.

### 2. Архитектура решения
1. **FastAPI Web Service**: Асинхронный веб-сервер с rate limiting (60 запр/мин) и поддержкой контекста (последние 2 шага).
2. **Entity Resolution**: Предварительное извлечение сущностей до обращения к SQL/LLM:
   - ИНН (9 цифр), номер сделки, код брокера (BK001..BK120).
   - 40 кодов ТН ВЭД с синонимами и морфологическими корнями.
   - Двуязычная нормализация сортов, классов и регионов.
3. **Deterministic Query Planner**: Мгновенное построение точного SQL для 15 основных типов вопросов.
4. **Provider-Agnostic LLM Fallback Chain**: Цепочка Gemini 2.5 Flash -> OpenAI с системным промптом и строгими ограничениями.
5. **SQL Guard**: Строгий SELECT-only, защита от инъекций, запрет DDL/DML, ограничение LIMIT 1000, 20s таймаут, read-only подключение к SQLite.
6. **Grounding Verifier**: Верификатор заземления проверяет каждое число ответа по строкам SQL.

### 3. Обработка ловушек датасета
- **Разные единицы измерения**: Бензин (литры и тонны) и другие товары никогда не суммируются в одну цифру — обязательно группируются по `unit`.
- **Разные валюты**: Экспортные сделки в USD конвертируются в сумы через `value_uzs` на дату сделки.
- **Аннулированные сделки (33 719)**: Исключаются из суммарных объемов продаж, но учитываются при прямом вопросе об аннулированных сделках.
- **Город Ташкент vs Ташкентская область**: Разделены на уровне сопоставления регионов (`Toshkent shahri` != `Toshkent viloyati`).
- **Пропущенные номера сделок (4 956)**: Проверяются по базе, агент честно сообщает об отсутствии сделки в реестре.
- **Просроченные поставки (17 805)**: Рассчитаны по контрактам (`delivery_date > payment_date + delivery_days`).

### 4. Реальные результаты тестирования
- **Golden тест-набор (50 вопросов: 25 RU, 25 UZ, 12 ловушек)**:
  - Успешно пройдено: **50 из 50 (100.0%)**
  - Среднее время ответа: **203.1 мс**
  - Максимальное время: **1.45 с** (при лимите 90 с)
- **Офлайн юнит-тесты (pytest)**: **10 из 10 успешно (0.11 с)**.
