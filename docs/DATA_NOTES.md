# DATA_NOTES.md — Verified Data Profile

> [!NOTE]
> All numbers verified by pandas profiling on 2026-11-05 against the actual CSV files
> in `data/raw/uzex_spot_data/uzex_spot_data/`.

## Files Overview

| File | Rows | Columns | Size |
|------|------|---------|------|
| brokers.csv | 120 | 4 | 7,403 B |
| participants.csv | 14,392 | 6 | 1,788,200 B |
| usd_rates.csv | 1,765 | 2 | 35,089 B |
| contracts.csv | 6,616 | 28 | 3,431,599 B |
| deals_2022.csv | 84,299 | 22 | 25,742,129 B |
| deals_2023.csv | 93,985 | 22 | 28,887,441 B |
| deals_2024.csv | 106,647 | 22 | 32,669,593 B |
| deals_2025.csv | 115,763 | 22 | 35,528,621 B |
| deals_2026.csv | 99,306 | 22 | 29,968,687 B |
| **Total deals** | **500,000** | | |

## Hypothesis Verification

### ✅ Confirmed
- **500,000 deals** across 2022–2026 (84,299 + 93,985 + 106,647 + 115,763 + 99,306).
- **6,616 contracts**, **14,392 participants** (392 sellers, 14,000 buyers), **120 brokers** (BK001–BK120).
- **INN = 9 digits** for all participants (verified: 100% are 9-char strings).
- **Deal period**: 03.01.2022 – 30.10.2026.
- **Deal IDs**: 100001–604956, all unique; 504,956 possible → **4,956 missing IDs**.
- **Money columns are TEXT with spaces** (e.g., `"304 547 938.4"`). Decimal separator is `.`.
- **Dates**: DD.MM.YYYY format throughout.
- **Domestic = UZS, Export = USD** (6,468 UZS contracts, 148 USD contracts; 493,410 domestic deals, 6,590 export deals).
- **Volume = Количество × Лот**. Unit price = Сумма / (Количество × Лот).
- **Стартовая цена** is per unit of measurement, NOT the final price.
- **Regions in two spellings**: deals/participants/brokers use Uzbek Latin (e.g., `Namangan viloyati`); contracts use Russian (e.g., `Наманганская область`). 14 regions in each.
- **"Toshkent shahri" ≠ "Toshkent viloyati"** (confirmed: both exist as separate entities).
- **Annulled deals**: 33,719 (`Аннулирован(Не оплачен)`) — these did NOT happen.
- **Lot values**: 1, 12, 100, 1000 (4 distinct values).
- **Units**: тонна, килограмм, литр, штука, куб.метр, кв.метр, метр (7 units — never sum different units).
- **TN VED codes**: 40 unique codes in contracts.
- **Product names**: 230 unique in contracts, 697 unique in deals (due to attribute combinations).
- **USD rates**: 1,765 daily rates covering 01.01.2022 – 30.10.2026.

### ⚠️ Corrected / Refined
- **Late deliveries**: ~17,800 (hypothesis said ~17.8k) — to be confirmed with exact computation (script running). Late delivery = Дата поставки > Дата оплаты + Срок поставки (days from contracts.csv).
- **Annulled count**: 33,719 (hypothesis said ~33.7k — confirmed).
- **Unique sellers in deals**: varies by year (136 in 2022, up to 335 in 2026) — not all 392 sellers have deals every year.
- **Buyer brokers**: all 120 brokers appear; seller brokers: only 116 appear as sellers.

## Status Distribution (All Deals)

| Status | Count | Notes |
|--------|-------|-------|
| Исполнен | 431,061 | Paid + fully delivered |
| Аннулирован(Не оплачен) | 33,719 | Cancelled — deal did NOT happen |
| Исполнен(Частично) | 22,648 | Paid, partially delivered (see Поставлено) |
| Оплачен | 5,854 | Paid, not yet delivered |
| Заключен | 3,954 | Forward/futures signed, payment not due |
| Ждёт оплату | 1,714 | Spot signed, payment not due |
| Новый | 964 | Created on last day (30.10.2026) |
| Не подписан | 86 | Not yet signed |

> [!IMPORTANT]
> Only 2026 deals have all 8 statuses. 2022–2024 have only 3 statuses (Исполнен, Аннулирован, Исполнен(Частично)) — all older deals resolved. 2025 has 3 statuses too (same). 2026 has all 8.

## Null Pattern
- **Дата оплаты, Дата поставки, Поставлено** are NULL together when deal is not paid/delivered (annulled, waiting, new, unsigned).
  - 2022: 5,732 nulls (= annulled count); 2023: 6,313; 2024: 7,323; 2025: 8,598; 2026: 18,471.
- **Contract attribute columns** (Марка, Размер, Сорт, Тип, Класс) are often NULL — attributes are embedded in Наименование продукта or Наименование товара instead.

## Key Columns Detail

### Contracts
- **Columns**: Номер контракта, Наименование продукта, Марка товара, Размер товара, Сорт товара, Тип товара, Класс товара, Код ТН ВЭД, Группа товара, Категория товара, Отрасль промышленности, Единица измерения, Лот, Валюта, Базисная цена, Сумма залога, Базис поставки, Регион, Адрес склада, Тип торгов, Тип контракта, Форма контракта, Срок оплаты, Срок поставки, Упаковка, ИНН продавца, Дата регистрации, Действует до
- **Группа товара**: "Высоколиквидные товары" (4,311) / "Прочие товары" (2,305)
- **Категория товара**: 8 categories (Сельскохозяйственная продукция 2097, Продовольственные товары 1462, Строительные материалы 1024, Нефтепродукты 675, Химическая продукция 416, Металлопродукция 355, Промышленные товары 331, Полимерная продукция 256)
- **Базис поставки**: EXW (5194), FCA (684), DAP (374), CPT (364)
- **Сумма залога**: 10% (6108), 15% (429), 20% (79)

### Deals
- **Columns**: Номер сделки, Дата сделки, Время сделки, Тип торгов, Количество, Сумма сделки, Стартовая цена, Номер контракта, Наименование товара, Лот, Единица измерения, Регион, Тип контракта, Форма контракта, Состояние сделки, ИНН продавца, ИНН покупателя, Брокер продавца, Брокер покупателя, Дата оплаты, Дата поставки, Поставлено
- **Тип торгов**: Английский аукцион (254,021), Двусторонний аукцион (235,504), Обратный аукцион (10,475)
- **Форма контракта**: Спот (456,724), Форвард (36,431), Фьючерс (6,845)

### Participants
- **Columns**: ИНН, Наименование, Регион, Вид деятельности, Роль, Плательщик НДС
- **Вид деятельности**: Торговая компания (7,011), Перерабатывающее предприятие (2,632), Транспортная компания (2,108), Производственное предприятие (1,874), Строительная компания (497), Производитель (157), Кластер (113)
- **Плательщик НДС**: Да (10,126), Нет (4,266)

### USD Rates
- **Columns**: Дата, Курс
- Daily rates from 01.01.2022 to 30.10.2026
- Sample: 01.01.2022 = 10829.1, rates increase over time

## Region Mapping (UZ Latin → Russian)

| Uzbek (in deals/participants/brokers) | Russian (in contracts) |
|---------------------------------------|----------------------|
| Toshkent shahri | г. Ташкент |
| Toshkent viloyati | Ташкентская область |
| Samarqand viloyati | Самаркандская область |
| Namangan viloyati | Наманганская область |
| Andijon viloyati | Андижанская область |
| Farg'ona viloyati | Ферганская область |
| Buxoro viloyati | Бухарская область |
| Qashqadaryo viloyati | Кашкадарьинская область |
| Surxondaryo viloyati | Сурхандарьинская область |
| Xorazm viloyati | Хорезмская область |
| Navoiy viloyati | Навоийская область |
| Jizzax viloyati | Джизакская область |
| Sirdaryo viloyati | Сырдарьинская область |
| Qoraqalpog'iston Respublikasi | Республика Каракалпакстан |

## Grade / Class Variants Found

### Сорт товара (28 variants)
Высший сорт, 1 сорт, 2 сорт, высший сорт, первый сорт, 1-сорта, 2-сорта, 3 сорт, ВЫСШИЙ СОРТ, 1 СОРТ, 2 СОРТ, ПЕРВЫЙ СОРТ, 3-сорта, высшего сорта, 3 СОРТ, I сорт, II сорт, etc.

### Класс товара (22 variants)
I класс, II класс, 2-класс, 2 класс, 1-класс, 1 класс, А500С, 3 класс, 4 класс, IV класс, III класс, 4-класс, 3-КЛАСС, 3-класс, 4-КЛАСС, II КЛАСС, 2-КЛАСС, I КЛАСС, IV КЛАСС, III КЛАСС, 1-КЛАСС, 2 КЛАСС

### Тип товара (16 variants)
хлебопекарная, обогащенная витаминно-минеральной смесью, рафинированное дезодорированное, тостированный, обрезные хвойных пород, дорожный, рафинированное, суспензионный, + uppercase variants

## Traps Summary

1. **Same product, different names**: "Хлопок-сырец (спот)" vs "Хлопок сырец (спот)" (with/without hyphen), "Мука пшеничная" vs "МУКА ПШЕНИЧНАЯ", "Портландцемент" vs "ПОРТЛАНДЦЕМЕНТ".
2. **Grade embedded in product name** in deals: "Шрот хлопковых семян Сорт первый сорт Тип тостированный".
3. **Contract regions in Russian, deal regions in Uzbek** — must map between them.
4. **Never sum different units**: тонна vs килограмм vs литр etc.
5. **Never sum different currencies**: UZS vs USD.
6. **Annulled deals (33,719)** must be excluded from "total sold" but included when explicitly asked about cancelled deals.
7. **"Поставлено" for partial deals**: actual delivered quantity in lots, not full.
8. **Broker appears in both columns**: count must specify seller-side, buyer-side, or both.
