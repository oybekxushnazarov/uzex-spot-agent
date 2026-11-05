# -*- coding: utf-8 -*-
"""Answer renderer: formats DB rows into clear, fluent text with an Evidence block."""

import re
from typing import Any, Optional
from app.dictionaries import (
    UNIT_RU, UNIT_UZ, CURRENCY_RU, CURRENCY_UZ,
    STATUS_RU, STATUS_UZ
)

def format_number(val: Any) -> str:
    """Format numbers with space thousands separators."""
    if val is None:
        return "—"
    if isinstance(val, (int,)):
        return f"{val:,}".replace(",", " ")
    if isinstance(val, (float,)):
        if val.is_integer():
            return f"{int(val):,}".replace(",", " ")
        return f"{val:,.2f}".replace(",", " ")
    try:
        f = float(str(val).replace(" ", ""))
        if f.is_integer():
            return f"{int(f):,}".replace(",", " ")
        return f"{f:,.2f}".replace(",", " ")
    except ValueError:
        return str(val)


def localize_text(text: str, lang: str) -> str:
    """Ensure text is in question language, translating any residual English LLM fragments."""
    if not text:
        return "Bekor qilingan bitimlar bundan mustasno" if lang == "uz" else "Без аннулированных сделок"
    
    replacements_uz = [
        (r"(?i)\bCount all deals\b", "Barcha bitimlarni hisoblash"),
        (r"(?i)\bCount the number of deals\b", "Bitimlar sonini hisoblash"),
        (r"(?i)\bCalculate total volume and value\b", "Umumiy hajm va summani hisoblash"),
        (r"(?i)\bCalculate total volume\b", "Umumiy hajmni hisoblash"),
        (r"(?i)\bCalculate total\b", "Jami miqdorni hisoblash"),
        (r"(?i)\bexcluding annulled deals\b", "bekor qilingan bitimlar bundan mustasno"),
        (r"(?i)\bexcluding annulled\b", "bekor qilinganlarsiz"),
        (r"(?i)\bgrouped by unit\b", "o'lchov birliklari bo'yicha guruhlangan"),
        (r"(?i)\bTop (\d+) brokers\b", r"Top-\1 ta broker"),
        (r"(?i)\bTop (\d+) products\b", r"Top-\1 ta mahsulot"),
        (r"(?i)\bTotal volume and value\b", "Umumiy hajm va summa"),
        (r"(?i)\bLook up deal\b", "Bitim ma'lumotlarini qidirish"),
        (r"(?i)\bAverage unit price\b", "O'rtacha narx"),
        (r"(?i)\bFind the maximum\b", "Maksimal qiymatni topish"),
        (r"(?i)\bfor the year\b", "yil bo'yicha"),
    ]
    replacements_ru = [
        (r"(?i)\bCount all deals\b", "Подсчет общего числа сделок"),
        (r"(?i)\bCount the number of deals\b", "Подсчет количества сделок"),
        (r"(?i)\bCalculate total volume and value\b", "Расчет общего объема и стоимости"),
        (r"(?i)\bCalculate total volume\b", "Расчет общего объема"),
        (r"(?i)\bCalculate total\b", "Расчет общей суммы"),
        (r"(?i)\bexcluding annulled deals\b", "исключая аннулированные сделки"),
        (r"(?i)\bexcluding annulled\b", "без аннулированных"),
        (r"(?i)\bgrouped by unit\b", "сгруппировано по единицам измерения"),
        (r"(?i)\bTop (\d+) brokers\b", r"Топ-\1 брокеров"),
        (r"(?i)\bTop (\d+) products\b", r"Топ-\1 товаров"),
        (r"(?i)\bTotal volume and value\b", "Общий объем и стоимость"),
        (r"(?i)\bLook up deal\b", "Поиск информации по сделке"),
        (r"(?i)\bAverage unit price\b", "Средняя цена за единицу"),
        (r"(?i)\bFind the maximum\b", "Поиск максимального значения"),
        (r"(?i)\bfor the year\b", "за год"),
    ]
    
    res = text
    rep_list = replacements_uz if lang == "uz" else replacements_ru
    for pat, rep in rep_list:
        res = re.sub(pat, rep, res)
    return res


def render_evidence_block(
    lang: str,
    interpretation: str,
    definition: str,
    row_count: int,
    sql: str,
    sample_deal_ids: list[int | str]
) -> str:
    """Render mandatory Evidence block at the bottom of the answer in question language."""
    samples_str = ", ".join(str(s) for s in sample_deal_ids) if sample_deal_ids else ("Не применимо" if lang == "ru" else "Tegishli emas")
    interp_clean = localize_text(interpretation, lang)
    def_clean = localize_text(definition, lang)
    
    if lang == "uz":
        return f"""
---
### Asos (Evidence)
- **Talqin va filtrlar**: {interp_clean}
- **Qo‘llanilgan ta’rif**: {def_clean}
- **Natija qatorlari soni**: {row_count}
- **Bajarilgan SQL**:
```sql
{sql.strip()}
```
- **Bitimlar namunalari (deal_id)**: {samples_str}
""".strip()
    else:
        return f"""
---
### Обоснование (Evidence)
- **Интерпретация и фильтры**: {interp_clean}
- **Примененное определение**: {def_clean}
- **Количество строк**: {row_count}
- **Выполненный SQL**:
```sql
{sql.strip()}
```
- **Примеры сделок (deal_id)**: {samples_str}
""".strip()


def render_table_or_rows(
    rows: list[tuple],
    cols: list[str],
    lang: str,
    max_rows: int = 10
) -> str:
    """Format rows as a Markdown table or list."""
    if not rows:
        return "Нет данных." if lang == "ru" else "Ma'lumot topilmadi."
        
    # If 1 row and 1 column:
    if len(rows) == 1 and len(cols) == 1:
        return format_number(rows[0][0])
        
    # Build markdown table
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows[:max_rows]:
        row_str = "| " + " | ".join(format_number(c) for c in r) + " |"
        lines.append(row_str)
        
    if len(rows) > max_rows:
        lines.append(f"*(всего {len(rows)} строк, показаны первые {max_rows})*" if lang == "ru" else f"*(jami {len(rows)} ta qator, dastlabki {max_rows} tasi ko'rsatilgan)*")
        
    return "\n".join(lines)
