# -*- coding: utf-8 -*-
"""Deterministic SQL planner and pattern matcher for the 15 core question types."""

import re
from typing import Optional, Any
from app.dictionaries import TN_VED_PRODUCTS, REGION_ALIASES

def plan_deterministic_query(
    question: str,
    entities: dict[str, Any],
    lang: str
) -> Optional[dict[str, Any]]:
    """
    Attempt to build an exact SQL plan deterministically from entities & query semantics.
    Returns: {"sql": str, "plan": str, "answer_template": str, "definition": str} or None.
    """
    t = question.lower()
    
    # ── TRAP 1: Injection attempt ──
    if entities.get("is_injection"):
        refusal = (
            "So'rovda ko'rsatmalarni chetlab o'tish aniqlandi. Men faqat birja ma'lumotlar bazasi asosida faktik javob beraman."
            if lang == "uz"
            else "В запросе обнаружена попытка обхода инструкций. Я отвечаю строго по фактам из базы данных биржи."
        )
        return {
            "sql": "SELECT 1 WHERE 1=0;",
            "plan": "Prompt injection attempt refused",
            "answer_template": refusal,
            "definition": "Refusal policy"
        }
        
    # ── TRAP 2: Out of data ──
    if entities.get("is_out_of_data"):
        reason = entities.get("out_of_data_reason", "")
        if lang == "uz":
            if entities.get("trap_type") == "trap_no_product":
                msg = "Ushbu tovar birjada sotilmaydi (UZEX ma'lumotlar to'plamida mavjud emas)."
            elif entities.get("trap_type") == "trap_forecast":
                msg = "Ma'lumotlar bazasida prognozlar va kelajak ma'lumotlari mavjud emas. Ma'lumotlar 03.01.2022 dan 30.10.2026 gacha bo'lgan davrni qamrab oladi."
            elif entities.get("trap_type") == "trap_no_field":
                msg = "Rahbarlar ismi, shaxsiy telefon raqamlari va manzillar birja ma'lumotlar to'plamida mavjud emas."
            elif entities.get("trap_type") == "trap_date_range":
                msg = f"Ko'rsatilgan sana ma'lumotlar to'plami davridan tashqarida (birja ma'lumotlari 03.01.2022 dan 30.10.2026 gacha)."
            elif entities.get("trap_type") in ("trap_no_data", "trap_missing_id"):
                deal_id = entities.get("deal_id", "")
                msg = f"{deal_id}-raqamli bitim ma'lumotlar bazasida mavjud emas (bitim raqamlaridagi oraliq yoki chegaradan tashqarida)."
            else:
                msg = f"Ma'lumotlar to'plamida ushbu so'rov bo'yicha ma'lumot mavjud emas: {reason}"
        else:
            if entities.get("trap_type") == "trap_no_product":
                msg = "Данный товар не торгуется на товарно-сырьевой бирже UZEX (отсутствует в реестре товаров)."
            elif entities.get("trap_type") == "trap_forecast":
                msg = "В базе данных нет прогнозов и оценок на будущее. Данные реестра охватывают фактический период с 03.01.2022 по 30.10.2026."
            elif entities.get("trap_type") == "trap_no_field":
                msg = "ФИО руководителей, личные телефоны и контактные лица отсутствуют в предоставленном датасете."
            elif entities.get("trap_type") == "trap_date_range":
                msg = "Запрошенная дата находится за пределами периода реестра (данные доступны с 03.01.2022 по 30.10.2026)."
            elif entities.get("trap_type") in ("trap_no_data", "trap_missing_id"):
                deal_id = entities.get("deal_id", "")
                msg = f"Сделка номер {deal_id} отсутствует в базе данных (пропуск в сквозной нумерации или номер вне диапазона)."
            else:
                msg = f"Запрошенные сведения отсутствуют в датасете: {reason}"
                
        return {
            "sql": "SELECT 1 WHERE 1=0;",
            "plan": "Out-of-data entity detected",
            "answer_template": msg,
            "definition": "Explicit refusal / not in dataset"
        }

    # ── 1. Single Deal Lookup ──
    if entities.get("deal_id"):
        did = entities["deal_id"]
        sql = f"SELECT deal_id, deal_date, deal_time, product_name, quantity, lot, volume, unit, amount, currency, unit_price, status, region_uz, region_ru, contract_type, contract_form, auction_type, seller_inn, buyer_inn, seller_broker, buyer_broker, payment_date, delivery_date, delivered, delivered_volume, is_late, value_uzs, tn_ved FROM deals WHERE deal_id = {did} LIMIT 1;"
        plan = f"Lookup deal by deal_id = {did}"
        defn = "Exact deal lookup by ID"
        if lang == "uz":
            tmpl = "Bitim #{deal_id} ({deal_date} {deal_time}): Mahsulot: {product_name}, Hajmi: {volume} {unit}, Summasi: {amount} {currency}, Birlik narxi: {unit_price} {currency}/{unit}, Holati: {status}, Sotuvchi STIR: {seller_inn}, Xaridor STIR: {buyer_inn}."
        else:
            tmpl = "Сделка №{deal_id} от {deal_date} {deal_time}: Товар: {product_name}, Объём: {volume} {unit}, Сумма: {amount} {currency}, Цена за ед.: {unit_price} {currency}/{unit}, Статус: {status}, ИНН продавца: {seller_inn}, ИНН покупателя: {buyer_inn}."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 2. Contract Lookup ──
    if entities.get("contract_id"):
        cid = entities["contract_id"]
        sql = f"SELECT contract_id, product_name, brand, size, sort, tn_ved, product_category, unit, lot, currency, base_price, region_uz, region_ru, delivery_days, payment_days, seller_inn FROM contracts WHERE contract_id = '{cid}' LIMIT 1;"
        plan = f"Lookup contract by contract_id = '{cid}'"
        defn = "Exact contract card lookup"
        if lang == "uz":
            tmpl = "Shartnoma #{contract_id}: Mahsulot: {product_name}, TN VED kodi: {tn_ved}, Toifa: {product_category}, Birlik: {unit}, Lot: {lot}, Valyuta: {currency}, Bazis narxi: {base_price}, Sotuvchi STIR: {seller_inn}."
        else:
            tmpl = "Карточка контракта №{contract_id}: Продукт: {product_name}, Код ТН ВЭД: {tn_ved}, Категория: {product_category}, Единица: {unit}, Лот: {lot}, Валюта: {currency}, Базисная цена: {base_price}, ИНН продавца: {seller_inn}."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 3. USD Rate on Specific Date ──
    if entities.get("date_iso") and any(kw in t for kw in ["курс", "kurs", "dollar", "usd"]):
        d_iso = entities["date_iso"]
        sql = f"SELECT date, rate FROM usd_rates WHERE date = '{d_iso}' LIMIT 1;"
        plan = f"Lookup USD exchange rate for date {d_iso}"
        defn = "Daily official USD exchange rate from usd_rates.csv"
        if lang == "uz":
            tmpl = "{date} holatiga ko'ra AQSh dollari kursi: 1 USD = {rate} so'm."
        else:
            tmpl = "Курс доллара США на дату {date}: 1 USD = {rate} сум."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 4. Participant Info by INN ──
    if entities.get("inn"):
        inn_val = entities["inn"]
        if any(kw in t for kw in ["сделк", "bitim", "совершил", "sotgan", "qancha bitim", "нечта", "сколько"]):
            if any(kw in t for kw in ["продавец", "sotuvchi"]):
                sql = f"SELECT COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total FROM deals WHERE seller_inn = '{inn_val}' AND is_annulled = 0;"
                plan = f"Count deals for seller INN {inn_val} excluding annulled"
                defn = "Annulled deals excluded; seller deals only"
                if lang == "uz":
                    tmpl = f"STIR {inn_val} bo'lgan sotuvchi tomonidan tuzilgan bitimlar soni: " + "{cnt} ta, umumiy qiymati: {total} so'm."
                else:
                    tmpl = f"Продавец с ИНН {inn_val} совершил " + "{cnt} сделок на общую сумму {total} сум."
            elif any(kw in t for kw in ["покупател", "xaridor"]):
                sql = f"SELECT COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total FROM deals WHERE buyer_inn = '{inn_val}' AND is_annulled = 0;"
                plan = f"Count deals for buyer INN {inn_val} excluding annulled"
                defn = "Annulled deals excluded; buyer deals only"
                if lang == "uz":
                    tmpl = f"STIR {inn_val} bo'lgan xaridor tomonidan tuzilgan bitimlar soni: " + "{cnt} ta, umumiy qiymati: {total} so'm."
                else:
                    tmpl = f"Покупатель с ИНН {inn_val} совершил " + "{cnt} сделок на общую сумму {total} сум."
            else:
                sql = f"SELECT 'seller' AS role, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total_uzs FROM deals WHERE seller_inn = '{inn_val}' AND is_annulled = 0 UNION ALL SELECT 'buyer' AS role, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total_uzs FROM deals WHERE buyer_inn = '{inn_val}' AND is_annulled = 0;"
                plan = f"Count deals and sum value for company INN {inn_val} as seller and buyer"
                defn = "Annulled deals excluded; seller and buyer counts separated"
                if lang == "uz":
                    tmpl = f"STIR {inn_val} bo'lgan korxona bitimlari (bekor qilinganlar hisobga olinmagan):\n" + "{table}"
                else:
                    tmpl = f"Сделки компании с ИНН {inn_val} (без аннулированных):\n" + "{table}"
        else:
            sql = f"SELECT inn, name, region_uz, region_ru, activity_type, role, vat_payer FROM participants WHERE inn = '{inn_val}' LIMIT 1;"
            plan = f"Lookup participant info for INN {inn_val}"
            defn = "Direct lookup from participants registry"
            if lang == "uz":
                tmpl = "Korxona: {name} (STIR: {inn})\nHudud: {region_uz}\nFaoliyat turi: {activity_type}\nBirjadagi roli: {role}\nQQS to'lovchisi: {vat_payer}."
            else:
                tmpl = "Компания: {name} (ИНН: {inn})\nРегион: {region_ru}\nВид деятельности: {activity_type}\nРоль на бирже: {role}\nПлательщик НДС: {vat_payer}."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 5. Broker Activity ──
    if entities.get("broker_code"):
        bk = entities["broker_code"]
        sql = f"SELECT 'seller_side' AS side, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total FROM deals WHERE seller_broker = '{bk}' AND is_annulled = 0 UNION ALL SELECT 'buyer_side' AS side, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total FROM deals WHERE buyer_broker = '{bk}' AND is_annulled = 0;"
        plan = f"Count broker {bk} transactions on seller side and buyer side"
        defn = "Both seller-side and buyer-side considered; annulled deals excluded"
        if lang == "uz":
            tmpl = f"Broker {bk} orqali tuzilgan bitimlar (sotuvchi va xaridor tomonida alohida, bekor qilinganlar hisobga olinmagan):\n" + "{table}"
        else:
            tmpl = f"Сделки с участием брокера {bk} (на стороне продавца и покупателя отдельно, без аннулированных):\n" + "{table}"
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 6. Late Deliveries ──
    if any(kw in t for kw in ["просроч", "кечик", "kechik", "muddati buzilgan", "срок поставки наруш"]):
        if entities.get("region_uz"):
            reg = entities["region_uz"]
            sql = f"SELECT COUNT(*) AS late_count, ROUND(SUM(value_uzs), 2) AS total_val FROM deals WHERE is_late = 1 AND region_uz = '{reg}';"
            plan = f"Count late deliveries in region {reg}"
            defn = "is_late=1 (delivery_date > payment_date + delivery_days from contract)"
            if lang == "uz":
                tmpl = "{region_uz} hududida yetkazib berish muddati buzilgan bitimlar soni: {late_count} ta, umumiy qiymati: {total_val} so'm."
            else:
                tmpl = "В регионе {region_uz} зарегистрировано {late_count} сделок с просроченной поставкой на общую сумму {total_val} сум."
        elif any(kw in t for kw in ["регион", "viloyat", "hudud", "qayerda", "где"]):
            sql = "SELECT region_uz, region_ru, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total_val FROM deals WHERE is_late = 1 GROUP BY region_uz ORDER BY cnt DESC LIMIT 5;"
            plan = "Top 5 regions by late delivery count"
            defn = "is_late=1 grouped by seller warehouse region"
            if lang == "uz":
                tmpl = "Yetkazib berish kechikishlari eng ko'p kuzatilgan dastlabki 5 ta hudud:\n{table}"
            else:
                tmpl = "Топ-5 регионов по количеству сделок с просроченной поставкой:\n{table}"
        else:
            sql = "SELECT COUNT(*) AS total_late, ROUND(SUM(value_uzs), 2) AS total_val FROM deals WHERE is_late = 1;"
            plan = "Total deals with late deliveries across all records"
            defn = "is_late=1 (delivery_date > payment_date + contract.delivery_days)"
            if lang == "uz":
                tmpl = "Jami {total_late} ta bitimda tovar yetkazib berish muddati buzilgan (shartnomada belgilangan muddatdan kech yetkazilgan). Umumiy qiymati: {total_val} so'm."
            else:
                tmpl = "Всего по бирже выявлено {total_late} сделок с просроченной поставкой (товар поставлен позже срока, установленного контрактом). Общая сумма: {total_val} сум."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 7. Annulled Deals Count ──
    if any(kw in t for kw in ["аннулир", "bekor qilingan", "bekor"]):
        sql = "SELECT COUNT(*) AS annulled_count, ROUND(SUM(value_uzs), 2) AS total_val FROM deals WHERE is_annulled = 1;"
        plan = "Count all annulled deals"
        defn = "Status = 'Аннулирован(Не оплачен)' (deals did not take place)"
        if lang == "uz":
            tmpl = "Jami bekor qilingan (muddatida to'lanmagan) bitimlar soni: {annulled_count} ta (umumiy qiymati {total_val} so'm). Ushbu bitimlar amalga oshmagan deb hisoblanadi."
        else:
            tmpl = "Всего аннулировано {annulled_count} сделок (не оплачены в установленный срок) на общую сумму {total_val} сум. Эти сделки не состоялись."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 8. Status Distribution ──
    if any(kw in t for kw in ["распределени", "статус", "holat", "holatlari", "taqsimot"]):
        sql = "SELECT status, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS val FROM deals GROUP BY status ORDER BY cnt DESC;"
        plan = "Distribution of all deals by status"
        defn = "All 500,000 deals grouped by status"
        if lang == "uz":
            tmpl = "Bitimlarning holatlar bo'yicha taqsimoti:\n{table}"
        else:
            tmpl = "Распределение сделок по статусам:\n{table}"
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 9. Export Deals ──
    if any(kw in t for kw in ["экспорт", "eksport", "export"]):
        sql = "SELECT COUNT(*) AS cnt, ROUND(SUM(amount), 2) AS usd_total, ROUND(SUM(value_uzs), 2) AS uzs_total FROM deals WHERE contract_type = 'Экспортный' AND is_annulled = 0;"
        plan = "Total export deals count and sum in USD and UZS equivalent"
        defn = "contract_type = 'Экспортный' excluding annulled deals; value_uzs converted at deal date rate"
        if lang == "uz":
            tmpl = "Eksport bitimlari bo'yicha umumiy ma'lumot (bekor qilinganlar hisobga olinmagan):\n- Jami bitimlar soni: {cnt} ta\n- Umumiy summasi: {usd_total} AQSh dollari\n- So'mdagi qiymati (bitim sanasidagi kurs bo'yicha): {uzs_total} so'm."
        else:
            tmpl = "Сводка по экспортным сделкам (без аннулированных):\n- Всего сделок: {cnt}\n- Сумма сделок: {usd_total} долл. США\n- Эквивалент в сумах (по курсу на дату каждой сделки): {uzs_total} сум."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 10. Toshkent shahri vs Toshkent viloyati Trap ──
    if ("ташкент" in t or "toshkent" in t) and ("город" in t or "shahri" in t or "шахри" in t) and ("област" in t or "viloyat" in t or "вилоят" in t):
        sql = "SELECT region_uz, region_ru, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total_val FROM deals WHERE region_uz IN ('Toshkent shahri', 'Toshkent viloyati') AND is_annulled = 0 GROUP BY region_uz;"
        plan = "Comparison of deal counts between Toshkent shahri and Toshkent viloyati"
        defn = "Separate administrative regions; annulled deals excluded"
        if lang == "uz":
            tmpl = "Toshkent shahri va Toshkent viloyati bo'yicha bitimlar (alohida ma'muriy hududlar, bekor qilinganlar hisobga olinmagan):\n{table}"
        else:
            tmpl = "Сравнение города Ташкента и Ташкентской области (отдельные регионы реестра, без аннулированных):\n{table}"
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 11. Average Price for Commodity ──
    if entities.get("tn_ved") and any(kw in t for kw in ["средн", "o'rtacha", "o‘rtacha", "narx", "цена"]):
        tn = entities["tn_ved"]
        p_name = entities["tn_ved_info"]["canon_uz_lat"] if lang == "uz" else entities["tn_ved_info"]["canon_ru"]
        y_cond = ""
        y_text = ""
        if entities.get("year"):
            y = entities["year"]
            y_cond = f" AND deal_date >= '{y}-01-01' AND deal_date <= '{y}-12-31'"
            y_text = f" в {y} году" if lang == "ru" else f" {y} yilda"
            
        sql = f"SELECT d.unit, d.currency, ROUND(AVG(d.unit_price), 2) AS avg_price, COUNT(*) AS cnt FROM deals d WHERE d.tn_ved = '{tn}'{y_cond} AND d.is_annulled = 0 GROUP BY d.unit, d.currency;"
        plan = f"Average unit price for {p_name} (TN VED {tn}){y_text}"
        defn = "unit_price = amount / volume; annulled deals excluded; grouped by unit and currency"
        if lang == "uz":
            tmpl = f"{p_name}{y_text} o'rtacha narxi (bekor qilingan bitimlar hisobga olinmagan):\n" + "{table}"
        else:
            tmpl = f"Средняя цена на товар «{p_name}»{y_text} (без аннулированных сделок):\n" + "{table}"
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 12. Total Volume for Commodity ──
    if entities.get("tn_ved") and any(kw in t for kw in ["объем", "объём", "hajm", "hajmi", "qancha", "сколько", "продано", "sotilgan"]):
        tn = entities["tn_ved"]
        p_name = entities["tn_ved_info"]["canon_uz_lat"] if lang == "uz" else entities["tn_ved_info"]["canon_ru"]
        y_cond = ""
        y_text = ""
        if entities.get("year"):
            y = entities["year"]
            y_cond = f" AND deal_date >= '{y}-01-01' AND deal_date <= '{y}-12-31'"
            y_text = f" в {y} году" if lang == "ru" else f" {y} yilda"
            
        sql = f"SELECT d.unit, SUM(d.volume) AS total_volume, COUNT(*) AS cnt, ROUND(SUM(d.value_uzs), 2) AS total_uzs FROM deals d WHERE d.tn_ved = '{tn}'{y_cond} AND d.is_annulled = 0 GROUP BY d.unit;"
        plan = f"Total sold volume for {p_name} (TN VED {tn}){y_text}"
        defn = "Volume = quantity * lot; annulled deals excluded"
        if lang == "uz":
            tmpl = f"{p_name}{y_text} bo'yicha sotuv hajmi (bekor qilingan bitimlar hisobga olinmagan):\n" + "{table}"
        else:
            tmpl = f"Объём реализации товара «{p_name}»{y_text} (без аннулированных сделок):\n" + "{table}"
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 13. Top Buyers / Top Sellers / Top Regions ──
    if any(kw in t for kw in ["топ", "top", "eng yirik", "крупнейш", "лидер", "лидир", "yetakchi", "eng ko'p", "eng kop", "eng ko‘p"]):
        if any(kw in t for kw in ["покупател", "xaridor"]):
            sql = "SELECT d.buyer_inn, p.name, COUNT(*) AS cnt, ROUND(SUM(d.value_uzs), 2) AS total_uzs FROM deals d JOIN participants p ON d.buyer_inn = p.inn WHERE d.is_annulled = 0 GROUP BY d.buyer_inn ORDER BY total_uzs DESC LIMIT 5;"
            plan = "Top 5 buyers by total purchase value in UZS"
            defn = "Annulled deals excluded; ranked by total value_uzs"
            if lang == "uz":
                tmpl = "Eng yirik 5 ta xaridor korxona (xarid summasi bo'yicha, bekor qilinganlar hisobga olinmagan):\n{table}"
            else:
                tmpl = "Топ-5 крупнейших покупателей по сумме сделок (без аннулированных):\n{table}"
            return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}
            
        elif any(kw in t for kw in ["продав", "sotuvchi"]):
            sql = "SELECT d.seller_inn, p.name, COUNT(*) AS cnt, ROUND(SUM(d.value_uzs), 2) AS total_uzs FROM deals d JOIN participants p ON d.seller_inn = p.inn WHERE d.is_annulled = 0 GROUP BY d.seller_inn ORDER BY total_uzs DESC LIMIT 5;"
            plan = "Top 5 sellers by total sales value in UZS"
            defn = "Annulled deals excluded; ranked by total value_uzs"
            if lang == "uz":
                tmpl = "Eng yirik 5 ta sotuvchi korxona (savdo summasi bo'yicha, bekor qilinganlar hisobga olinmagan):\n{table}"
            else:
                tmpl = "Топ-5 крупнейших продавцов по сумме реализации (без аннулированных):\n{table}"
            return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}
            
        elif any(kw in t for kw in ["регион", "viloyat", "hudud"]):
            sql = "SELECT region_uz, region_ru, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total_uzs FROM deals WHERE is_annulled = 0 GROUP BY region_uz ORDER BY cnt DESC LIMIT 5;"
            plan = "Top 5 regions by number of deals"
            defn = "Ranked by deal count; annulled excluded"
            if lang == "uz":
                tmpl = "Bitimlar soni bo'yicha yetakchi 5 ta hudud:\n{table}"
            else:
                tmpl = "Топ-5 регионов-лидеров по количеству сделок:\n{table}"
            return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 14. Largest Deal by Sum ──
    if any(kw in t for kw in ["крупная", "крупнейшая", "katta", "eng katta", "максимальн", "rekord"]):
        sql = "SELECT deal_id, deal_date, product_name, volume, unit, amount, currency, value_uzs, status FROM deals WHERE is_annulled = 0 ORDER BY value_uzs DESC LIMIT 1;"
        plan = "Find single largest deal by total value in UZS"
        defn = "Ranked by value_uzs DESC (amount converted to UZS); annulled excluded"
        if lang == "uz":
            tmpl = "UZEX birjasidagi eng yirik bitim (so'mdagi qiymat bo'yicha):\nBitim raqami: #{deal_id}\nSana: {deal_date}\nMahsulot: {product_name}\nHajmi: {volume} {unit}\nSummasi: {amount} {currency} (qiymati: {value_uzs} so'm)\nHolati: {status}."
        else:
            tmpl = "Самая крупная сделка на бирже UZEX (по сумме в сумах):\nНомер сделки: №{deal_id}\nДата: {deal_date}\nТовар: {product_name}\nОбъём: {volume} {unit}\nСумма: {amount} {currency} (эквивалент: {value_uzs} сум)\nСтатус: {status}."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 15. Deals Count by Year (Time Series) ──
    if any(kw in t for kw in ["по годам", "каждый год", "har yili", "yillar bo'yicha", "yillar boyicha", "dinamika"]):
        sql = "SELECT SUBSTR(deal_date, 1, 4) AS year, COUNT(*) AS cnt, ROUND(SUM(value_uzs), 2) AS total_uzs FROM deals GROUP BY year ORDER BY year;"
        plan = "Deals count and total value grouped by year"
        defn = "All deals grouped by year of deal_date"
        if lang == "uz":
            tmpl = "Yillar bo'yicha bitimlar soni va umumiy summasi:\n{table}"
        else:
            tmpl = "Динамика количества и сумм сделок по годам:\n{table}"
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 16. Total Contracts Count ──
    if any(kw in t for kw in ["контракт", "shartnoma", "kontrakt"]) and any(kw in t for kw in ["всего", "jami", "сколько", "nechta"]):
        sql = "SELECT COUNT(*) AS total_contracts FROM contracts;"
        plan = "Count total registered contracts"
        defn = "All rows in contracts table"
        if lang == "uz":
            tmpl = "Birjada jami {total_contracts} ta kontrakt ro'yxatga olingan."
        else:
            tmpl = "Всего в реестре зарегистрировано {total_contracts} контрактов."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    # ── 17. Total Deals Count (Global) ──
    if any(kw in t for kw in ["всего сделок", "jami nechta bitim", "сколько всего сделок", "jami bitimlar soni", "в базе данных"]):
        sql = "SELECT COUNT(*) AS total_deals FROM deals;"
        plan = "Count all deals in the database"
        defn = "All records in deals table (period 03.01.2022 - 30.10.2026)"
        if lang == "uz":
            tmpl = "Ma'lumotlar bazasida jami {total_deals} ta bitim mavjud (03.01.2022 dan 30.10.2026 gacha bo'lgan davr)."
        else:
            tmpl = "Всего в базе данных зарегистрировано {total_deals} сделок за период с 03.01.2022 по 30.10.2026."
        return {"sql": sql, "plan": plan, "answer_template": tmpl, "definition": defn}

    return None
