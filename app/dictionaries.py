# -*- coding: utf-8 -*-
"""
dictionaries.py — Complete canonical dictionaries for the UZEX AI agent.

Contains:
- TN_VED_PRODUCTS: TN VED code → product info (canonical names RU/UZ, synonyms)
- REGION_UZ_TO_RU / REGION_RU_TO_UZ: region name mappings
- STATUS_WORDS: deal status translations RU/UZ
- UNIT_WORDS: unit of measurement translations
- CURRENCY_WORDS: currency translations
- GRADE_NORM: grade/class/sort normalization tables
"""

from __future__ import annotations

# ────────────────────────────────────────────────────────────────
# TN VED → Product Dictionary
# ────────────────────────────────────────────────────────────────
# For each TN VED code: canonical RU name, UZ Latin name, UZ Cyrillic name,
# synonyms (all variants that appear in data or might appear in user questions),
# unit, category, industry.

TN_VED_PRODUCTS: dict[str, dict] = {
    "100199": {
        "canon_ru": "Пшеница продовольственная",
        "canon_uz_lat": "Bug'doy (oziq-ovqat)",
        "canon_uz_cyr": "Буғдой (озиқ-овқат)",
        "synonyms": ["пшеница", "bug'doy", "buğdoy", "буғдой", "wheat", "пшеница продовольственная"],
        "unit": "тонна",
        "category": "Сельскохозяйственная продукция",
        "industry": "Сельское хозяйство",
        "group": "Высоколиквидные товары",
    },
    "100630": {
        "canon_ru": "Рис шлифованный",
        "canon_uz_lat": "Guruch (silliqlangan)",
        "canon_uz_cyr": "Гуруч (силлиқланган)",
        "synonyms": ["рис", "guruch", "гуруч", "rice", "рис шлифованный"],
        "unit": "тонна",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Прочие товары",
    },
    "110100": {
        "canon_ru": "Мука пшеничная",
        "canon_uz_lat": "Bug'doy uni",
        "canon_uz_cyr": "Буғдой уни",
        "synonyms": ["мука", "мука пшеничная", "un", "bug'doy uni", "буғдой уни", "flour", "мука высший сорт", "мука 1 сорт", "мука 2 сорт"],
        "unit": "килограмм",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Высоколиквидные товары",
    },
    "151219": {
        "canon_ru": "Масло подсолнечное",
        "canon_uz_lat": "Kungaboqar yog'i",
        "canon_uz_cyr": "Кунгабоқар ёғи",
        "synonyms": ["масло подсолнечное", "подсолнечное масло", "kungaboqar yog'i", "кунгабоқар ёғи", "sunflower oil"],
        "unit": "тонна",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Прочие товары",
    },
    "151229": {
        "canon_ru": "Масло хлопковое",
        "canon_uz_lat": "Paxta yog'i",
        "canon_uz_cyr": "Пахта ёғи",
        "synonyms": ["масло хлопковое", "хлопковое масло", "paxta yog'i", "пахта ёғи", "cottonseed oil", "paxtayog'i"],
        "unit": "тонна",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Высоколиквидные товары",
    },
    "170199": {
        "canon_ru": "Сахар белый",
        "canon_uz_lat": "Oq shakar",
        "canon_uz_cyr": "Оқ шакар",
        "synonyms": ["сахар", "сахар белый", "сахар-песок", "shakar", "шакар", "sugar", "oq shakar"],
        "unit": "тонна",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Высоколиквидные товары",
    },
    "220190": {
        "canon_ru": "Вода питьевая",
        "canon_uz_lat": "Ichimlik suvi",
        "canon_uz_cyr": "Ичимлик суви",
        "synonyms": ["вода", "вода питьевая", "питьевая вода", "suv", "ichimlik suvi", "ичимлик суви", "water"],
        "unit": "штука",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Прочие товары",
    },
    "230610": {
        "canon_ru": "Шрот хлопковых семян",
        "canon_uz_lat": "Paxta urug'i shroti",
        "canon_uz_cyr": "Пахта уруғи шроти",
        "synonyms": ["шрот", "шрот хлопковых семян", "шрот хлопковый", "shrot", "paxta shroti", "пахта шроти", "cottonseed meal"],
        "unit": "килограмм",
        "category": "Сельскохозяйственная продукция",
        "industry": "Сельское хозяйство",
        "group": "Прочие товары",
    },
    "230990": {
        "canon_ru": "Комбикорм",
        "canon_uz_lat": "Omixta yem",
        "canon_uz_cyr": "Омихта ем",
        "synonyms": ["комбикорм", "комбикорма", "omixta yem", "feed", "корм"],
        "unit": "килограмм",
        "category": "Сельскохозяйственная продукция",
        "industry": "Сельское хозяйство",
        "group": "Прочие товары",
    },
    "250100": {
        "canon_ru": "Соль",
        "canon_uz_lat": "Tuz",
        "canon_uz_cyr": "Туз",
        "synonyms": ["соль", "соль поваренная", "tuz", "туз", "salt"],
        "unit": "тонна",
        "category": "Продовольственные товары",
        "industry": "Пищевая промышленность",
        "group": "Прочие товары",
    },
    "252020": {
        "canon_ru": "Гипс строительный",
        "canon_uz_lat": "Qurilish gipsi",
        "canon_uz_cyr": "Қурилиш гипси",
        "synonyms": ["гипс", "гипс строительный", "gips", "гипси", "gypsum"],
        "unit": "тонна",
        "category": "Строительные материалы",
        "industry": "Строительная индустрия",
        "group": "Прочие товары",
    },
    "252210": {
        "canon_ru": "Известь",
        "canon_uz_lat": "Ohak",
        "canon_uz_cyr": "Оҳак",
        "synonyms": ["известь", "известь строительная", "ohak", "оҳак", "lime"],
        "unit": "тонна",
        "category": "Строительные материалы",
        "industry": "Строительная индустрия",
        "group": "Прочие товары",
    },
    "252329": {
        "canon_ru": "Портландцемент",
        "canon_uz_lat": "Portlandsement",
        "canon_uz_cyr": "Портландсемент",
        "synonyms": ["цемент", "портландцемент", "sement", "семент", "cement", "portlandsement"],
        "unit": "тонна",
        "category": "Строительные материалы",
        "industry": "Строительная индустрия",
        "group": "Прочие товары",
    },
    "271012": {
        "canon_ru": "Бензин автомобильный",
        "canon_uz_lat": "Avtomobil benzini",
        "canon_uz_cyr": "Автомобил бензини",
        "synonyms": ["бензин", "бензин автомобильный", "benzin", "бензини", "gasoline", "аи-80", "аи-92", "аи-95"],
        "unit": "литр",
        "category": "Нефтепродукты",
        "industry": "Нефтегазовая промышленность",
        "group": "Высоколиквидные товары",
    },
    "271019": {
        "canon_ru": "Дизельное топливо",
        "canon_uz_lat": "Dizel yoqilg'isi",
        "canon_uz_cyr": "Дизел ёқилғиси",
        "synonyms": ["дизель", "дизельное топливо", "топливо дизельное", "dizel", "дизел", "diesel"],
        "unit": "литр",
        "category": "Нефтепродукты",
        "industry": "Нефтегазовая промышленность",
        "group": "Высоколиквидные товары",
    },
    "271112": {
        "canon_ru": "Сжиженный газ",
        "canon_uz_lat": "Suyultirilgan gaz",
        "canon_uz_cyr": "Суюлтирилган газ",
        "synonyms": ["газ", "сжиженный газ", "gaz", "газ сжиженный", "lpg", "пба", "пбт"],
        "unit": "тонна",
        "category": "Нефтепродукты",
        "industry": "Нефтегазовая промышленность",
        "group": "Высоколиквидные товары",
    },
    "271320": {
        "canon_ru": "Битум нефтяной",
        "canon_uz_lat": "Neft bitumi",
        "canon_uz_cyr": "Нефт битуми",
        "synonyms": ["битум", "битум нефтяной", "bitum", "битуми", "bitumen"],
        "unit": "тонна",
        "category": "Нефтепродукты",
        "industry": "Нефтегазовая промышленность",
        "group": "Высоколиквидные товары",
    },
    "280421": {
        "canon_ru": "Аргон газообразный",
        "canon_uz_lat": "Argon (gazsimon)",
        "canon_uz_cyr": "Аргон (газсимон)",
        "synonyms": ["аргон", "аргон газообразный", "argon", "аргон газ"],
        "unit": "куб.метр",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Прочие товары",
    },
    "280430": {
        "canon_ru": "Азот",
        "canon_uz_lat": "Azot",
        "canon_uz_cyr": "Азот",
        "synonyms": ["азот", "azot", "nitrogen"],
        "unit": "куб.метр",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Прочие товары",
    },
    "280700": {
        "canon_ru": "Кислота серная",
        "canon_uz_lat": "Sulfat kislotasi",
        "canon_uz_cyr": "Сулфат кислотаси",
        "synonyms": ["кислота серная", "серная кислота", "kislota", "кислотаси", "sulfuric acid"],
        "unit": "тонна",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Прочие товары",
    },
    "281511": {
        "canon_ru": "Гидроксид натрия (сода каустическая)",
        "canon_uz_lat": "Natriy gidroksidi",
        "canon_uz_cyr": "Натрий гидроксиди",
        "synonyms": ["сода каустическая", "сода", "natriy gidroksidi", "натрий гидроксиди", "caustic soda", "гидроксид натрия"],
        "unit": "тонна",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Прочие товары",
    },
    "310210": {
        "canon_ru": "Карбамид (мочевина)",
        "canon_uz_lat": "Karbamid (siydik moddasi)",
        "canon_uz_cyr": "Карбамид (сийдик моддаси)",
        "synonyms": ["карбамид", "мочевина", "karbamid", "карбамид", "urea"],
        "unit": "тонна",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Высоколиквидные товары",
    },
    "310230": {
        "canon_ru": "Аммиачная селитра",
        "canon_uz_lat": "Ammiakli selitra",
        "canon_uz_cyr": "Аммиакли селитра",
        "synonyms": ["селитра", "аммиачная селитра", "selitra", "селитра", "ammonium nitrate"],
        "unit": "тонна",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Высоколиквидные товары",
    },
    "320810": {
        "canon_ru": "Эмаль ПФ-115",
        "canon_uz_lat": "Emal PF-115",
        "canon_uz_cyr": "Эмал ПФ-115",
        "synonyms": ["эмаль", "эмаль пф-115", "краска", "emal", "эмал", "paint", "emal pf-115"],
        "unit": "килограмм",
        "category": "Химическая продукция",
        "industry": "Химическая промышленность",
        "group": "Прочие товары",
    },
    "390120": {
        "canon_ru": "Полиэтилен",
        "canon_uz_lat": "Polietilen",
        "canon_uz_cyr": "Полиэтилен",
        "synonyms": ["полиэтилен", "полиэтилен гранулированный", "polietilen", "полиэтилен", "polyethylene"],
        "unit": "тонна",
        "category": "Полимерная продукция",
        "industry": "Химическая промышленность",
        "group": "Высоколиквидные товары",
    },
    "390210": {
        "canon_ru": "Полипропилен",
        "canon_uz_lat": "Polipropilen",
        "canon_uz_cyr": "Полипропилен",
        "synonyms": ["полипропилен", "полипропилен гранулированный", "polipropilen", "полипропилен", "polypropylene"],
        "unit": "тонна",
        "category": "Полимерная продукция",
        "industry": "Химическая промышленность",
        "group": "Высоколиквидные товары",
    },
    "390410": {
        "canon_ru": "Поливинилхлорид",
        "canon_uz_lat": "Polivinilxlorid",
        "canon_uz_cyr": "Поливинилхлорид",
        "synonyms": ["пвх", "поливинилхлорид", "pvx", "поливинилхлорид", "pvc"],
        "unit": "тонна",
        "category": "Полимерная продукция",
        "industry": "Химическая промышленность",
        "group": "Высоколиквидные товары",
    },
    "391721": {
        "canon_ru": "Трубы полиэтиленовые",
        "canon_uz_lat": "Polietilen quvurlar",
        "canon_uz_cyr": "Полиэтилен қувурлар",
        "synonyms": ["трубы", "трубы полиэтиленовые", "труба пэ", "quvur", "қувурлар", "pe pipes"],
        "unit": "метр",
        "category": "Полимерная продукция",
        "industry": "Химическая промышленность",
        "group": "Прочие товары",
    },
    "440711": {
        "canon_ru": "Пиломатериалы",
        "canon_uz_lat": "Taxta materiallar",
        "canon_uz_cyr": "Тахта материаллар",
        "synonyms": ["пиломатериал", "пиломатериалы", "пиломатериал обрезной", "taxta", "тахта", "lumber", "доска"],
        "unit": "куб.метр",
        "category": "Строительные материалы",
        "industry": "Лесная промышленность",
        "group": "Прочие товары",
    },
    "520100": {
        "canon_ru": "Хлопок-сырец",
        "canon_uz_lat": "Paxta xom ashyosi",
        "canon_uz_cyr": "Пахта хом ашёси",
        "synonyms": ["хлопок", "хлопок-сырец", "хлопок сырец", "paxta", "пахта", "cotton", "cotton raw", "хлопок спот", "хлопок форвард", "хлопок фьючерс"],
        "unit": "килограмм",
        "category": "Сельскохозяйственная продукция",
        "industry": "Сельское хозяйство",
        "group": "Высоколиквидные товары",
    },
    "520512": {
        "canon_ru": "Пряжа хлопчатобумажная",
        "canon_uz_lat": "Paxta ipi",
        "canon_uz_cyr": "Пахта ипи",
        "synonyms": ["пряжа", "пряжа хлопчатобумажная", "пряжа хлопковая", "ip", "пахта ипи", "cotton yarn"],
        "unit": "тонна",
        "category": "Сельскохозяйственная продукция",
        "industry": "Текстильная промышленность",
        "group": "Прочие товары",
    },
    "690410": {
        "canon_ru": "Кирпич керамический",
        "canon_uz_lat": "Keramik g'isht",
        "canon_uz_cyr": "Керамик ғишт",
        "synonyms": ["кирпич", "кирпич керамический", "g'isht", "ғишт", "brick"],
        "unit": "штука",
        "category": "Строительные материалы",
        "industry": "Строительная индустрия",
        "group": "Прочие товары",
    },
    "700529": {
        "canon_ru": "Стекло листовое",
        "canon_uz_lat": "Varaqli oyna",
        "canon_uz_cyr": "Варақли ойна",
        "synonyms": ["стекло", "стекло листовое", "стекло флоат", "oyna", "ойна", "glass"],
        "unit": "кв.метр",
        "category": "Строительные материалы",
        "industry": "Строительная индустрия",
        "group": "Прочие товары",
    },
    "720853": {
        "canon_ru": "Лист стальной горячекатаный",
        "canon_uz_lat": "Po'lat list (issiq prokatlangan)",
        "canon_uz_cyr": "Пўлат лист (иссиқ прокатланган)",
        "synonyms": ["лист стальной", "лист стальной горячекатаный", "po'lat list", "пўлат лист", "steel sheet", "hot rolled steel"],
        "unit": "килограмм",
        "category": "Металлопродукция",
        "industry": "Металлургия",
        "group": "Прочие товары",
    },
    "721420": {
        "canon_ru": "Арматура стальная",
        "canon_uz_lat": "Po'lat armatura",
        "canon_uz_cyr": "Пўлат арматура",
        "synonyms": ["арматура", "арматура стальная", "armatura", "арматура", "rebar", "steel rebar"],
        "unit": "тонна",
        "category": "Металлопродукция",
        "industry": "Металлургия",
        "group": "Высоколиквидные товары",
    },
    "721710": {
        "canon_ru": "Проволока арматурная",
        "canon_uz_lat": "Armatura simi",
        "canon_uz_cyr": "Арматура сими",
        "synonyms": ["проволока", "проволока арматурная", "sim", "сими", "wire"],
        "unit": "килограмм",
        "category": "Металлопродукция",
        "industry": "Металлургия",
        "group": "Прочие товары",
    },
    "740311": {
        "canon_ru": "Катод медный",
        "canon_uz_lat": "Mis katod",
        "canon_uz_cyr": "Мис катод",
        "synonyms": ["катод", "катод медный", "медный катод", "mis", "мис катод", "copper cathode"],
        "unit": "тонна",
        "category": "Металлопродукция",
        "industry": "Металлургия",
        "group": "Высоколиквидные товары",
    },
    "760421": {
        "canon_ru": "Профиль алюминиевый",
        "canon_uz_lat": "Alyuminiy profil",
        "canon_uz_cyr": "Алюминий профил",
        "synonyms": ["профиль", "профиль алюминиевый", "алюминиевый профиль", "alyuminiy", "алюминий", "aluminum profile"],
        "unit": "килограмм",
        "category": "Металлопродукция",
        "industry": "Металлургия",
        "group": "Прочие товары",
    },
    "848210": {
        "canon_ru": "Подшипник",
        "canon_uz_lat": "Podshipnik",
        "canon_uz_cyr": "Подшипник",
        "synonyms": ["подшипник", "podshipnik", "bearing"],
        "unit": "штука",
        "category": "Промышленные товары",
        "industry": "Машиностроение",
        "group": "Прочие товары",
    },
    "854449": {
        "canon_ru": "Кабель силовой",
        "canon_uz_lat": "Kuch kabeli",
        "canon_uz_cyr": "Куч кабели",
        "synonyms": ["кабель", "кабель силовой", "kabel", "кабел", "power cable"],
        "unit": "метр",
        "category": "Промышленные товары",
        "industry": "Электротехническая промышленность",
        "group": "Прочие товары",
    },
}


# ────────────────────────────────────────────────────────────────
# Region Mapping
# ────────────────────────────────────────────────────────────────

REGION_UZ_TO_RU: dict[str, str] = {
    "Toshkent shahri": "г. Ташкент",
    "Toshkent viloyati": "Ташкентская область",
    "Samarqand viloyati": "Самаркандская область",
    "Namangan viloyati": "Наманганская область",
    "Andijon viloyati": "Андижанская область",
    "Farg'ona viloyati": "Ферганская область",
    "Buxoro viloyati": "Бухарская область",
    "Qashqadaryo viloyati": "Кашкадарьинская область",
    "Surxondaryo viloyati": "Сурхандарьинская область",
    "Xorazm viloyati": "Хорезмская область",
    "Navoiy viloyati": "Навоийская область",
    "Jizzax viloyati": "Джизакская область",
    "Sirdaryo viloyati": "Сырдарьинская область",
    "Qoraqalpog'iston Respublikasi": "Республика Каракалпакстан",
}

REGION_RU_TO_UZ: dict[str, str] = {v: k for k, v in REGION_UZ_TO_RU.items()}

# Also map common user inputs to the canonical UZ key used in deals
REGION_ALIASES: dict[str, str] = {
    # Russian full
    "ташкент": "Toshkent shahri",
    "город ташкент": "Toshkent shahri",
    "ташкентская область": "Toshkent viloyati",
    "самаркандская область": "Samarqand viloyati",
    "самарканд": "Samarqand viloyati",
    "наманганская область": "Namangan viloyati",
    "наманган": "Namangan viloyati",
    "андижанская область": "Andijon viloyati",
    "андижан": "Andijon viloyati",
    "ферганская область": "Farg'ona viloyati",
    "фергана": "Farg'ona viloyati",
    "бухарская область": "Buxoro viloyati",
    "бухара": "Buxoro viloyati",
    "кашкадарьинская область": "Qashqadaryo viloyati",
    "кашкадарья": "Qashqadaryo viloyati",
    "сурхандарьинская область": "Surxondaryo viloyati",
    "сурхандарья": "Surxondaryo viloyati",
    "хорезмская область": "Xorazm viloyati",
    "хорезм": "Xorazm viloyati",
    "навоийская область": "Navoiy viloyati",
    "навои": "Navoiy viloyati",
    "джизакская область": "Jizzax viloyati",
    "джизак": "Jizzax viloyati",
    "сырдарьинская область": "Sirdaryo viloyati",
    "сырдарья": "Sirdaryo viloyati",
    "республика каракалпакстан": "Qoraqalpog'iston Respublikasi",
    "каракалпакстан": "Qoraqalpog'iston Respublikasi",
    "г. ташкент": "Toshkent shahri",
    # Uzbek Latin
    "toshkent": "Toshkent shahri",
    "toshkent shahri": "Toshkent shahri",
    "toshkent viloyati": "Toshkent viloyati",
    "samarqand": "Samarqand viloyati",
    "namangan": "Namangan viloyati",
    "andijon": "Andijon viloyati",
    "farg'ona": "Farg'ona viloyati",
    "fergana": "Farg'ona viloyati",
    "buxoro": "Buxoro viloyati",
    "qashqadaryo": "Qashqadaryo viloyati",
    "surxondaryo": "Surxondaryo viloyati",
    "xorazm": "Xorazm viloyati",
    "navoiy": "Navoiy viloyati",
    "jizzax": "Jizzax viloyati",
    "sirdaryo": "Sirdaryo viloyati",
    "qoraqalpog'iston": "Qoraqalpog'iston Respublikasi",
}


# ────────────────────────────────────────────────────────────────
# Status Words (RU / UZ)
# ────────────────────────────────────────────────────────────────

STATUS_RU: dict[str, str] = {
    "Исполнен": "Оплачен и полностью поставлен",
    "Исполнен(Частично)": "Оплачен, поставлен частично",
    "Оплачен": "Оплачен, ожидается поставка",
    "Заключен": "Подписан (форвард/фьючерс), оплата не наступила",
    "Ждёт оплату": "Подписан (спот), ожидает оплату",
    "Новый": "Заключен 30.10.2026 (последний день)",
    "Не подписан": "Ещё не подписан сторонами",
    "Аннулирован(Не оплачен)": "Не оплачен вовремя, аннулирован — сделка не состоялась",
}

STATUS_UZ: dict[str, str] = {
    "Исполнен": "To'langan va to'liq yetkazilgan",
    "Исполнен(Частично)": "To'langan, qisman yetkazilgan",
    "Оплачен": "To'langan, yetkazish kutilmoqda",
    "Заключен": "Imzolangan (forvard/fyuchers), to'lov muddati kelmagan",
    "Ждёт оплату": "Imzolangan (spot), to'lovni kutmoqda",
    "Новый": "30.10.2026 kuni (oxirgi kun) tuzilgan",
    "Не подписан": "Hali tomonlar imzolamagan",
    "Аннулирован(Не оплачен)": "Muddatida to'lanmagan va bekor qilingan — bitim amalga oshmagan",
}


# ────────────────────────────────────────────────────────────────
# Unit Words (RU / UZ)
# ────────────────────────────────────────────────────────────────

UNIT_RU: dict[str, str] = {
    "тонна": "тонн",
    "килограмм": "кг",
    "литр": "литров",
    "штука": "шт.",
    "куб.метр": "куб.м",
    "кв.метр": "кв.м",
    "метр": "м",
}

UNIT_UZ: dict[str, str] = {
    "тонна": "tonna",
    "килограмм": "kg",
    "литр": "litr",
    "штука": "dona",
    "куб.метр": "kub.m",
    "кв.метр": "kv.m",
    "метр": "m",
}


# ────────────────────────────────────────────────────────────────
# Currency Words (RU / UZ)
# ────────────────────────────────────────────────────────────────

CURRENCY_RU: dict[str, str] = {
    "UZS": "сум",
    "USD": "долл. США",
}

CURRENCY_UZ: dict[str, str] = {
    "UZS": "so'm",
    "USD": "AQSh dollari",
}


# ────────────────────────────────────────────────────────────────
# Grade / Sort Normalization
# ────────────────────────────────────────────────────────────────

SORT_NORM: dict[str, str] = {
    "высший сорт": "высший сорт",
    "высшего сорта": "высший сорт",
    "в/с": "высший сорт",
    "1 сорт": "1 сорт",
    "1-сорта": "1 сорт",
    "1-сорт": "1 сорт",
    "первый сорт": "1 сорт",
    "i сорт": "1 сорт",
    "2 сорт": "2 сорт",
    "2-сорта": "2 сорт",
    "второй сорт": "2 сорт",
    "ii сорт": "2 сорт",
    "3 сорт": "3 сорт",
    "3-сорта": "3 сорт",
    "третий сорт": "3 сорт",
    "iii сорт": "3 сорт",
}

CLASS_NORM: dict[str, str] = {
    "1 класс": "1 класс",
    "1-класс": "1 класс",
    "i класс": "1 класс",
    "2 класс": "2 класс",
    "2-класс": "2 класс",
    "ii класс": "2 класс",
    "3 класс": "3 класс",
    "3-класс": "3 класс",
    "iii класс": "3 класс",
    "4 класс": "4 класс",
    "4-класс": "4 класс",
    "iv класс": "4 класс",
    "а500с": "А500С",
}

TYPE_NORM: dict[str, str] = {
    "хлебопекарная": "хлебопекарная",
    "обогащенная витаминно-минеральной смесью": "обогащенная витаминно-минеральной смесью",
    "рафинированное дезодорированное": "рафинированное дезодорированное",
    "тостированный": "тостированный",
    "обрезные хвойных пород": "обрезные хвойных пород",
    "дорожный": "дорожный",
    "рафинированное": "рафинированное",
    "суспензионный": "суспензионный",
    "техническая": "техническая",
    "йодированная": "йодированная",
    "твердая": "твердая",
}


# ────────────────────────────────────────────────────────────────
# Contract Type / Form words
# ────────────────────────────────────────────────────────────────

CONTRACT_TYPE_RU = {"Внутренний": "Внутренний", "Экспортный": "Экспортный"}
CONTRACT_TYPE_UZ = {"Внутренний": "Ichki", "Экспортный": "Eksport"}

CONTRACT_FORM_RU = {"Спот": "Спот", "Форвард": "Форвард", "Фьючерс": "Фьючерс"}
CONTRACT_FORM_UZ = {"Спот": "Spot", "Форвард": "Forvard", "Фьючерс": "Fyuchers"}

AUCTION_TYPE_RU = {
    "Английский аукцион": "Английский аукцион (цена растёт)",
    "Обратный аукцион": "Обратный аукцион (цена снижается)",
    "Двусторонний аукцион": "Двусторонний аукцион",
}
AUCTION_TYPE_UZ = {
    "Английский аукцион": "Ingliz auktsioni (narx ko'tariladi)",
    "Обратный аукцион": "Teskari auktsion (narx tushadi)",
    "Двусторонний аукцион": "Ikki tomonlama auktsion",
}


# ────────────────────────────────────────────────────────────────
# Data boundaries (for out-of-data detection)
# ────────────────────────────────────────────────────────────────

DATA_DATE_MIN = "2022-01-03"  # first deal date
DATA_DATE_MAX = "2026-10-30"  # last deal date
DEAL_ID_MIN = 100001
DEAL_ID_MAX = 604956
TOTAL_DEALS = 500000
MISSING_DEAL_IDS = 4956
