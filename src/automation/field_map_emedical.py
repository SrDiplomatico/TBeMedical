"""
eMedical field mapping - I-693 data model to eMedical web form selectors.

These selectors need to be updated based on actual eMedical form inspection.
Use browser DevTools to identify correct selectors for each field.

The form has approximately 4 pages with various next/submit/ok buttons.
"""

import re

# Country name to eMedical country code mapping
# These codes match the actual dropdown values in eMedical
# Includes every country from the eMedical dropdown plus common alternative
# spellings/names that may appear on I-693 forms.
COUNTRY_CODE_MAP = {
    # A
    "afghanistan": "AFGH",
    "albania": "ALBA",
    "algeria": "ALGE",
    "american samoa": "ASAM",
    "andorra": "ANDO",
    "angola": "ANGA",
    "anguilla": "ANGU",
    "antarctica": "ANTA",
    "antigua and barbuda": "ANBA",
    "antigua": "ANBA",
    "argentina": "ARGE",
    "armenia": "ARME",
    "aruba": "ARUB",
    "australia": "A",
    "austria": "AUST",
    "azerbaijan": "AZER",
    # B
    "bahamas": "BHMS",
    "the bahamas": "BHMS",
    "bahrain": "BAHR",
    "bangladesh": "BDES",
    "barbados": "BARS",
    "belarus": "BYEL",
    "belgium": "BELM",
    "belize": "BELZ",
    "benin": "BENI",
    "bermuda": "BERM",
    "bhutan": "BHUT",
    "bolivia": "BOLI",
    "bonaire": "BSES",
    "bonaire, saint e & s": "BSES",
    "bonaire, sint eustatius and saba": "BSES",
    "bosnia": "BOHE",
    "bosnia and herzegovina": "BOHE",
    "bosnia & herzegovina": "BOHE",
    "botswana": "BOTS",
    "brazil": "BRAZ",
    "brasil": "BRAZ",
    "british indian ocean territory": "BIOT",
    "brit indian ocn terr": "BIOT",
    "brunei": "BRUI",
    "brunei darussalam": "BRUI",
    "bulgaria": "BULG",
    "burkina faso": "UVOL",
    "burma": "BURM",
    "burundi": "BURU",
    # C
    "cabo verde": "CABV",
    "cape verde": "CVER",
    "cambodia": "CAMB",
    "cameroon": "CREP",
    "canada": "CANA",
    "cayman islands": "CAIS",
    "central african republic": "CARE",
    "central african rep": "CARE",
    "chad": "CHAD",
    "chile": "CHIL",
    "china": "PRCH",
    "china, peoples republic of": "PRCH",
    "peoples republic of china": "PRCH",
    "people's republic of china": "PRCH",
    "prc": "PRCH",
    "christmas island": "CSIS",
    "cocos islands": "COCO",
    "cocos (keeling) islands": "COCO",
    "colombia": "COLA",
    "comoros": "COMO",
    "congo": "CONG",
    "republic of the congo": "CONG",
    "congo, republic of": "CONG",
    "republic of congo": "CONG",
    "democratic republic of the congo": "DRCO",
    "democratic republic of congo": "DRCO",
    "congo, dem republic": "DRCO",
    "dem rep of the congo": "DRCO",
    "dem rep of congo": "DRCO",
    "drc": "DRCO",
    "cook islands": "COOI",
    "costa rica": "CRIC",
    "cote d'ivoire": "ICOA",
    "cote divoire": "ICOA",
    "ivory coast": "ICOA",
    "croatia": "CROA",
    "cuba": "CUBA",
    "curacao": "CURA",
    "cyprus": "CYPR",
    "czech republic": "CZER",
    "czechia": "CZEH",
    "czechoslovakia": "CZEC",
    # D
    "denmark": "DENM",
    "djibouti": "JIBU",
    "dominica": "DOMI",
    "dominican republic": "DREP",
    # E
    "ecuador": "ECUA",
    "egypt": "EGYP",
    "el salvador": "ESAL",
    "equatorial guinea": "EQGN",
    "eritrea": "ERIT",
    "estonia": "ESTO",
    "eswatini": "ESWA",
    "swaziland": "SWAZ",
    "ethiopia": "ETHI",
    # F
    "falkland islands": "FALI",
    "faroe islands": "FAIS",
    "fiji": "FIJI",
    "finland": "FINL",
    "france": "FRAE",
    "french guiana": "GUYE",
    "french polynesia": "FPOL",
    # G
    "gabon": "GABO",
    "gambia": "GAMB",
    "the gambia": "GAMB",
    "georgia": "GEOG",
    "germany": "GERM",
    "ghana": "GHAN",
    "gibraltar": "GIBR",
    "greece": "GREE",
    "greenland": "GRED",
    "grenada": "GREN",
    "guadeloupe": "GUAE",
    "guam": "GUAM",
    "guatemala": "GUAT",
    "guernsey": "GUER",
    "guinea": "GUIN",
    "guinea-bissau": "GUBS",
    "guinea bissau": "GUBS",
    "guyana": "GUYN",
    # H
    "haiti": "HAIT",
    "hong kong": "HKON",
    "hksar": "HKON",
    "hksar of the prc": "HKON",
    "honduras": "HOND",
    "hungary": "HUNG",
    # I
    "iceland": "ICEL",
    "india": "INDI",
    "indonesia": "INDO",
    "iran": "IRAN",
    "islamic republic of iran": "IRAN",
    "iraq": "IRAQ",
    "ireland": "IREP",
    "isle of man": "IMAN",
    "israel": "ISRA",
    "italy": "ITAL",
    # J
    "jamaica": "JAMA",
    "japan": "JAPA",
    "jersey": "JERS",
    "jordan": "JORD",
    # K
    "kazakhstan": "KAZA",
    "kenya": "KENY",
    "kiribati": "GIIS",
    "korea, north": "NKOR",
    "north korea": "NKOR",
    "dprk": "NKOR",
    "korea, south": "SKOR",
    "south korea": "SKOR",
    "korea": "SKOR",
    "republic of korea": "SKOR",
    "kosovo": "KOSO",
    "kuwait": "KUWA",
    "kyrgyzstan": "KIRG",
    # L
    "laos": "LAOS",
    "lao": "LAOS",
    "lao peoples dem rep": "LAOS",
    "lao people's democratic republic": "LAOS",
    "latvia": "LATV",
    "lebanon": "LEBA",
    "lesotho": "LESO",
    "liberia": "LIBE",
    "libya": "LIBY",
    "liechtenstein": "LIEC",
    "lithuania": "LITH",
    "luxembourg": "LUXE",
    # M
    "macau": "MACA",
    "macao": "MACA",
    "madagascar": "MADA",
    "malawi": "MALW",
    "malaysia": "MALS",
    "maldives": "MIS",
    "mali": "M",
    "malta": "MALT",
    "marshall islands": "MAIS",
    "martinique": "MART",
    "mauritania": "MAUA",
    "mauritius": "MAUS",
    "mayotte": "MAYO",
    "mexico": "MEXI",
    "micronesia": "FSOM",
    "micronesia, fed stat": "FSOM",
    "federated states of micronesia": "FSOM",
    "moldova": "MOLD",
    "monaco": "MONA",
    "mongolia": "MONG",
    "montenegro": "MNTE",
    "montserrat": "MONT",
    "morocco": "MORO",
    "mozambique": "MOZA",
    "myanmar": "MYAN",
    # N
    "namibia": "NAMI",
    "nauru": "NAUR",
    "nepal": "NEPA",
    "netherlands": "NETH",
    "holland": "NETH",
    "the netherlands": "NETH",
    "netherlands antilles": "NANT",
    "new caledonia": "NCAL",
    "new zealand": "NZEA",
    "nicaragua": "NICA",
    "niger": "NIGR",
    "nigeria": "NGRA",
    "niue": "NIUE",
    "norfolk island": "NOIS",
    "north macedonia": "NMAC",
    "macedonia": "NMAC",
    "fyr macedonia": "MKDA",
    "republic of north macedonia": "NMAC",
    "northern mariana islands": "NMAI",
    "norway": "NORW",
    # O
    "oman": "OMAN",
    # P
    "pakistan": "PKSN",
    "palau": "PALA",
    "palestine": "PSTE",
    "palestine, state of": "PSTE",
    "state of palestine": "PSTE",
    "palestinian authority": "PALE",
    "panama": "PANA",
    "papua new guinea": "NGUI",
    "png": "NGUI",
    "paraguay": "PARA",
    "peru": "PERU",
    "philippines": "PHIL",
    "the philippines": "PHIL",
    "pitcairn": "PIIS",
    "poland": "POLA",
    "portugal": "PORL",
    "puerto rico": "PRIC",
    # Q
    "qatar": "QATA",
    # R
    "reunion": "REIS",
    "romania": "ROUM",
    "russia": "RFED",
    "russian federation": "RFED",
    "rwanda": "RWAN",
    # S
    "saint lucia": "STLU",
    "st lucia": "STLU",
    "st. lucia": "STLU",
    "samoa": "SAMO",
    "san marino": "SMAR",
    "sao tome and principe": "STPR",
    "sao tome & principe": "STPR",
    "saudi arabia": "SAAR",
    "senegal": "SENE",
    "serbia": "SERB",
    "serbia and montenegro": "SEMO",
    "serbia & montenegro": "SEMO",
    "seychelles": "SEYC",
    "sierra leone": "SLEO",
    "singapore": "SING",
    "sint maarten": "SXMN",
    "sint maarten (dutch part)": "SXMN",
    "slovakia": "SVKA",
    "slovenia": "SLOV",
    "solomon islands": "SOLI",
    "somalia": "SOMA",
    "south africa": "SAFR",
    "south sudan": "SSDN",
    "spain": "SPAI",
    "sri lanka": "SRIL",
    "st barthelemy": "STBA",
    "saint barthelemy": "STBA",
    "st helena": "SHTC",
    "saint helena": "SHTC",
    "st kitts and nevis": "SCKN",
    "saint kitts and nevis": "SCKN",
    "st kitts": "SCKN",
    "st martin": "STMA",
    "saint martin": "STMA",
    "st pierre and miquelon": "STPM",
    "st pierre & miquelon": "STPM",
    "saint pierre and miquelon": "STPM",
    "st vincent and the grenadines": "STVG",
    "st vincent": "STVG",
    "saint vincent": "STVG",
    "saint vincent and the grenadines": "STVG",
    "sudan": "SUDA",
    "suriname": "SURI",
    "surinam": "SURI",
    "svalbard": "SAJM",
    "svalbard and jan mayen": "SAJM",
    "svalbard & jan mayen": "SAJM",
    "sweden": "SWED",
    "switzerland": "SWIT",
    "syria": "SYRI",
    "syrian arab republic": "SYRI",
    # T
    "taiwan": "TAIW",
    "tajikistan": "TADZ",
    "tanzania": "TANZ",
    "thailand": "THAI",
    "timor-leste": "TILE",
    "timor leste": "TILE",
    "east timor": "TILE",
    "togo": "TOGO",
    "tokelau": "TOKE",
    "tonga": "TONG",
    "trinidad and tobago": "TRIN",
    "trinidad": "TRIN",
    "trinidad & tobago": "TRIN",
    "tunisia": "TUNI",
    "turkey": "TURE",
    "turkiye": "TURE",
    "turkmenistan": "TURM",
    "turks and caicos islands": "TCIS",
    "turks and caicos": "TCIS",
    "tuvalu": "TUVU",
    # U
    "ussr": "USSR",
    "u.s.s.r.": "USSR",
    "soviet union": "USSR",
    "uganda": "UGAN",
    "ukraine": "UKRA",
    "united arab emirates": "UAEM",
    "uae": "UAEM",
    "united kingdom": "UK",
    "uk": "UK",
    "england": "UK",
    "great britain": "UK",
    "britain": "UK",
    "scotland": "UK",
    "wales": "UK",
    "northern ireland": "UK",
    "united states": "USA",
    "united states of america": "USA",
    "usa": "USA",
    "us": "USA",
    "unknown": "UNKN",
    "uruguay": "URUG",
    "uzbekistan": "UZBE",
    # V
    "vanuatu": "VANU",
    "vatican city": "VCIT",
    "vatican": "VCIT",
    "vatican city state": "VCIT",
    "holy see": "VCIT",
    "venezuela": "VENE",
    "vietnam": "VIET",
    "viet nam": "VIET",
    "virgin islands (u.s)": "VIIS",
    "virgin islands": "VIIS",
    "us virgin islands": "VIIS",
    "u.s. virgin islands": "VIIS",
    "british virgin islands": "VIUK",
    "virgin islands (british)": "VIUK",
    # W
    "wallis and futuna": "WAFU",
    "wallis & futuna": "WAFU",
    "western sahara": "WSHR",
    # Y
    "yemen": "YEME",
    "yemen, republic of": "YEME",
    "republic of yemen": "YEME",
    "yugoslavia": "YUGO",
    # Z
    "zaire": "ZAIR",
    "zambia": "ZAMB",
    "zimbabwe": "ZIMB",
}


def get_country_code(country_name: str) -> str:
    """Convert country name to eMedical country code."""
    if not country_name:
        return ""
    normalized = country_name.lower().strip()
    return COUNTRY_CODE_MAP.get(normalized, "")


# Issuing country uses different codes (ISO 3166-1 alpha-3 style)
# Comprehensive list matching all eMedical dropdown countries plus common alternatives
ISSUING_COUNTRY_CODE_MAP = {
    # A
    "afghanistan": "AFG",
    "albania": "ALB",
    "algeria": "DZA",
    "american samoa": "ASM",
    "andorra": "AND",
    "angola": "AGO",
    "anguilla": "AIA",
    "antarctica": "ATA",
    "antigua and barbuda": "ATG",
    "antigua": "ATG",
    "argentina": "ARG",
    "armenia": "ARM",
    "aruba": "ABW",
    "australia": "AUS",
    "austria": "AUT",
    "azerbaijan": "AZE",
    # B
    "bahamas": "BHS",
    "the bahamas": "BHS",
    "bahrain": "BHR",
    "bangladesh": "BGD",
    "barbados": "BRB",
    "belarus": "BLR",
    "belgium": "BEL",
    "belize": "BLZ",
    "benin": "BEN",
    "bermuda": "BMU",
    "bhutan": "BTN",
    "bolivia": "BOL",
    "bonaire": "BES",
    "bonaire, sint eustatius and saba": "BES",
    "bosnia": "BIH",
    "bosnia and herzegovina": "BIH",
    "bosnia & herzegovina": "BIH",
    "botswana": "BWA",
    "brazil": "BRA",
    "brasil": "BRA",
    "british indian ocean territory": "IOT",
    "brunei": "BRN",
    "brunei darussalam": "BRN",
    "bulgaria": "BGR",
    "burkina faso": "BFA",
    "burma": "BUR",
    "myanmar": "MMR",
    "burundi": "BDI",
    # C
    "cabo verde": "CPV",
    "cape verde": "CPV",
    "cambodia": "KHM",
    "cameroon": "CMR",
    "canada": "CAN",
    "cayman islands": "CYM",
    "central african republic": "CAF",
    "central african rep": "CAF",
    "chad": "TCD",
    "chile": "CHL",
    "china": "CHN",
    "china, peoples republic of": "CHN",
    "peoples republic of china": "CHN",
    "people's republic of china": "CHN",
    "prc": "CHN",
    "christmas island": "CXR",
    "cocos islands": "CCK",
    "cocos (keeling) islands": "CCK",
    "colombia": "COL",
    "comoros": "COM",
    "congo": "COG",
    "republic of the congo": "COG",
    "congo, republic of": "COG",
    "republic of congo": "COG",
    "democratic republic of the congo": "COD",
    "democratic republic of congo": "COD",
    "congo, dem republic": "COD",
    "dem rep of the congo": "COD",
    "dem rep of congo": "COD",
    "drc": "COD",
    "cook islands": "COK",
    "costa rica": "CRI",
    "cote d'ivoire": "CIV",
    "cote divoire": "CIV",
    "ivory coast": "CIV",
    "croatia": "HRV",
    "cuba": "CUB",
    "curacao": "CUW",
    "cyprus": "CYP",
    "czech republic": "CZE",
    "czechia": "CZE",
    "czechoslovakia": "CSK",
    # D
    "denmark": "DNK",
    "djibouti": "DJI",
    "dominica": "DMA",
    "dominican republic": "DOM",
    # E
    "ecuador": "ECU",
    "egypt": "EGY",
    "el salvador": "SLV",
    "equatorial guinea": "GNQ",
    "eritrea": "ERI",
    "estonia": "EST",
    "eswatini": "SWZ",
    "swaziland": "SWZ",
    "ethiopia": "ETH",
    # F
    "falkland islands": "FLK",
    "faroe islands": "FRO",
    "fiji": "FJI",
    "finland": "FIN",
    "france": "FRA",
    "french guiana": "GUF",
    "french polynesia": "PYF",
    # G
    "gabon": "GAB",
    "gambia": "GMB",
    "the gambia": "GMB",
    "georgia": "GEO",
    "germany": "D",
    "ghana": "GHA",
    "gibraltar": "GIB",
    "greece": "GRC",
    "greenland": "GRL",
    "grenada": "GRD",
    "guadeloupe": "GLP",
    "guam": "GUM",
    "guatemala": "GTM",
    "guernsey": "GGY",
    "guinea": "GIN",
    "guinea-bissau": "GNB",
    "guinea bissau": "GNB",
    "guyana": "GUY",
    # H
    "haiti": "HTI",
    "hong kong": "HKG",
    "hksar": "HKG",
    "hksar of the prc": "HKG",
    "honduras": "HND",
    "hungary": "HUN",
    # I
    "iceland": "ISL",
    "india": "IND",
    "indonesia": "IDN",
    "iran": "IRN",
    "islamic republic of iran": "IRN",
    "iraq": "IRQ",
    "ireland": "IRL",
    "isle of man": "IMN",
    "israel": "ISR",
    "italy": "ITA",
    # J
    "jamaica": "JAM",
    "japan": "JPN",
    "jersey": "JEY",
    "jordan": "JOR",
    # K
    "kazakhstan": "KAZ",
    "kenya": "KEN",
    "kiribati": "KIR",
    "korea, north": "PRK",
    "north korea": "PRK",
    "dprk": "PRK",
    "korea, south": "KOR",
    "south korea": "KOR",
    "korea": "KOR",
    "republic of korea": "KOR",
    "kosovo": "XKX",
    "kuwait": "KWT",
    "kyrgyzstan": "KGZ",
    # L
    "laos": "LAO",
    "lao": "LAO",
    "lao peoples dem rep": "LAO",
    "lao people's democratic republic": "LAO",
    "latvia": "LVA",
    "lebanon": "LBN",
    "lesotho": "LSO",
    "liberia": "LBR",
    "libya": "LBY",
    "liechtenstein": "LIE",
    "lithuania": "LTU",
    "luxembourg": "LUX",
    # M
    "macau": "MAC",
    "macao": "MAC",
    "madagascar": "MDG",
    "malawi": "MWI",
    "malaysia": "MYS",
    "maldives": "MDV",
    "mali": "MLI",
    "malta": "MLT",
    "marshall islands": "MHL",
    "martinique": "MTQ",
    "mauritania": "MRT",
    "mauritius": "MUS",
    "mayotte": "MYT",
    "mexico": "MEX",
    "micronesia": "FSM",
    "federated states of micronesia": "FSM",
    "moldova": "MDA",
    "monaco": "MCO",
    "mongolia": "MNG",
    "montenegro": "MNE",
    "montserrat": "MSR",
    "morocco": "MAR",
    "mozambique": "MOZ",
    # N
    "namibia": "NAM",
    "nauru": "NRU",
    "nepal": "NPL",
    "netherlands": "NLD",
    "holland": "NLD",
    "the netherlands": "NLD",
    "netherlands antilles": "ANT",
    "new caledonia": "NCL",
    "new zealand": "NZL",
    "nicaragua": "NIC",
    "niger": "NER",
    "nigeria": "NGA",
    "niue": "NIU",
    "norfolk island": "NFK",
    "north macedonia": "MKD",
    "macedonia": "MKD",
    "fyr macedonia": "MKD",
    "republic of north macedonia": "MKD",
    "northern mariana islands": "MNP",
    "norway": "NOR",
    # O
    "oman": "OMN",
    # P
    "pakistan": "PAK",
    "palau": "PLW",
    "palestine": "PSE",
    "palestine, state of": "PSE",
    "state of palestine": "PSE",
    "palestinian authority": "PSE",
    "panama": "PAN",
    "papua new guinea": "PNG",
    "png": "PNG",
    "paraguay": "PRY",
    "peru": "PER",
    "philippines": "PHL",
    "the philippines": "PHL",
    "pitcairn": "PCN",
    "poland": "POL",
    "portugal": "PRT",
    "puerto rico": "PRI",
    # Q
    "qatar": "QAT",
    # R
    "reunion": "REU",
    "romania": "ROU",
    "russia": "RUS",
    "russian federation": "RUS",
    "rwanda": "RWA",
    # S
    "saint lucia": "LCA",
    "st lucia": "LCA",
    "st. lucia": "LCA",
    "samoa": "WSM",
    "san marino": "SMR",
    "sao tome and principe": "STP",
    "sao tome & principe": "STP",
    "saudi arabia": "SAU",
    "senegal": "SEN",
    "serbia": "SRB",
    "serbia and montenegro": "SCG",
    "serbia & montenegro": "SCG",
    "seychelles": "SYC",
    "sierra leone": "SLE",
    "singapore": "SGP",
    "sint maarten": "SXM",
    "sint maarten (dutch part)": "SXM",
    "slovakia": "SVK",
    "slovenia": "SVN",
    "solomon islands": "SLB",
    "somalia": "SOM",
    "south africa": "ZAF",
    "south sudan": "SSD",
    "spain": "ESP",
    "sri lanka": "LKA",
    "st barthelemy": "BLM",
    "saint barthelemy": "BLM",
    "st helena": "SHN",
    "saint helena": "SHN",
    "st kitts and nevis": "KNA",
    "saint kitts and nevis": "KNA",
    "st kitts": "KNA",
    "st martin": "MAF",
    "saint martin": "MAF",
    "st pierre and miquelon": "SPM",
    "st pierre & miquelon": "SPM",
    "saint pierre and miquelon": "SPM",
    "st vincent and the grenadines": "VCT",
    "st vincent": "VCT",
    "saint vincent": "VCT",
    "saint vincent and the grenadines": "VCT",
    "sudan": "SDN",
    "suriname": "SUR",
    "surinam": "SUR",
    "svalbard": "SJM",
    "svalbard and jan mayen": "SJM",
    "sweden": "SWE",
    "switzerland": "CHE",
    "syria": "SYR",
    "syrian arab republic": "SYR",
    # T
    "taiwan": "TWN",
    "tajikistan": "TJK",
    "tanzania": "TZA",
    "thailand": "THA",
    "timor-leste": "TLS",
    "timor leste": "TLS",
    "east timor": "TLS",
    "togo": "TGO",
    "tokelau": "TKL",
    "tonga": "TON",
    "trinidad and tobago": "TTO",
    "trinidad": "TTO",
    "trinidad & tobago": "TTO",
    "tunisia": "TUN",
    "turkey": "TUR",
    "turkiye": "TUR",
    "turkmenistan": "TKM",
    "turks and caicos islands": "TCA",
    "turks and caicos": "TCA",
    "tuvalu": "TUV",
    # U
    "ussr": "SUN",
    "u.s.s.r.": "SUN",
    "soviet union": "SUN",
    "uganda": "UGA",
    "ukraine": "UKR",
    "united arab emirates": "ARE",
    "uae": "ARE",
    "united kingdom": "GBR",
    "uk": "GBR",
    "england": "GBR",
    "great britain": "GBR",
    "britain": "GBR",
    "scotland": "GBR",
    "wales": "GBR",
    "northern ireland": "GBR",
    "united states": "USA",
    "united states of america": "USA",
    "usa": "USA",
    "us": "USA",
    "unknown": "XXX",
    "uruguay": "URY",
    "uzbekistan": "UZB",
    # V
    "vanuatu": "VUT",
    "vatican city": "VAT",
    "vatican": "VAT",
    "vatican city state": "VAT",
    "holy see": "VAT",
    "venezuela": "VEN",
    "vietnam": "VNM",
    "viet nam": "VNM",
    "virgin islands (u.s)": "VIR",
    "virgin islands": "VIR",
    "us virgin islands": "VIR",
    "u.s. virgin islands": "VIR",
    "british virgin islands": "VGB",
    "virgin islands (british)": "VGB",
    # W
    "wallis and futuna": "WLF",
    "wallis & futuna": "WLF",
    "western sahara": "ESH",
    # Y
    "yemen": "YEM",
    "yemen, republic of": "YEM",
    "republic of yemen": "YEM",
    "yugoslavia": "YUG",
    # Z
    "zaire": "ZAR",
    "zambia": "ZMB",
    "zimbabwe": "ZWE",
}


def get_issuing_country_code(country_name: str) -> str:
    """Convert country name to issuing country code (ISO 3166-1 alpha-3 style)."""
    if not country_name:
        return ""
    normalized = country_name.lower().strip()
    return ISSUING_COUNTRY_CODE_MAP.get(normalized, "")


# Characters eMedical accepts in name fields: letters (including accented),
# spaces, hyphens and apostrophes.  Anything else — most commonly a trailing
# period on an abbreviated given name such as "MA." — is rejected with
# "The following characters are not supported".
_NAME_DISALLOWED_RE = re.compile(r"[^A-Za-z\u00C0-\u024F' -]")
_NAME_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_name(value: str) -> str:
    """
    Strip characters eMedical rejects from a name before typing it into a
    name field.

    Removes periods, commas, digits and other punctuation, collapses repeated
    whitespace, and trims leading/trailing spaces, hyphens and apostrophes.

    Args:
        value: Raw name from the I-693

    Returns:
        Name containing only eMedical-supported characters
    """
    if not value:
        return ""

    cleaned = _NAME_DISALLOWED_RE.sub(" ", value)
    cleaned = _NAME_WHITESPACE_RE.sub(" ", cleaned)
    return cleaned.strip(" -'")


# Page 1: Applicant basic information (search/create case page)
# Note: Page 1 is just the case search - only needs name, DOB, and ID number
PAGE1_FIELDS = {
    # Status Adjuster dropdown - must be selected first
    "status_adjuster": {
        "selector": "#caseSearch-_0d3c2b_input",
        "type": "html_select",
        "static_value": "STSADJ",  # Always select "Status Adjuster"
    },
    "applicant.family_name": {
        "selector": "#caseSearch-familyName_input",
        "type": "text",
        "sanitize_name": True,  # eMedical rejects periods and other punctuation
    },
    "applicant.given_name": {
        "selector": "#caseSearch-givenNames_input",
        "type": "text",
        "sanitize_name": True,  # e.g. "MA." -> "MA"
    },
    "applicant.date_of_birth": {
        "selector": "#caseSearch-dob_input",
        "type": "date",
        "format": "DD/MM/YYYY",  # Australian date format
    },
    # Identity Document Number from Part 5.2 of I-693 (NOT A-Number)
    # Strip dashes and special characters - eMedical only accepts alphanumeric
    "applicant.id_number": {
        "selector": "#caseSearch-identityDocumentNumber_input",
        "type": "text",
        "strip_special_chars": True,  # Remove dashes, spaces, etc.
    },
}

# Page 2: Additional applicant details
PAGE2_FIELDS = {
    # Sex dropdown - standard HTML select, values are M/F
    "sex": {
        "selector": "#_0e0ch0b0a0a0c1_input",  # The actual <select> element
        "type": "html_select",
        "data_path": "applicant.sex",
        # No value_map needed - I-693 already has M/F which matches the option values
    },
    # Country of birth - standard HTML select with country codes
    "country_of_birth": {
        "selector": "#_0e0ch0b0a0a0e1_input",  # The actual <select> element
        "type": "html_select",
        "data_path": "applicant.country_of_birth",
        "use_country_code": True,  # Flag to convert country name to code
    },
    # City of birth - text field
    "city_of_birth": {
        "selector": "#_0e0ch0b0a0a0f1_input",
        "type": "text",
        "data_path": "applicant.city_of_birth",
    },
    # Prior country of residence - standard HTML select (use country of birth)
    "prior_country": {
        "selector": "#_0e0ch0b0a0a0g1_input",  # UPDATE with actual selector
        "type": "html_select",
        "data_path": "applicant.country_of_birth",  # Default to country of birth
        "use_country_code": True,
    },
    # Identity document type - standard HTML select
    "id_type": {
        "selector": "#_0e0ch0b1a0a0a1_input",  # Corrected selector
        "type": "html_select",
        "data_path": "applicant.id_type",
        "use_id_type_code": True,  # Use get_page5_id_type_code() for keyword matching
        "fallback_value": "06",  # Use "Other" if ID type not in value_map
        "value_map": {
            "Passport": "01",
            "passport": "01",
            "PASSPORT": "01",
            "Original Passport": "01",
            "National ID card": "07",
            "National ID": "07",
            "national id": "07",
            "NATIONAL ID": "07",
            "Identity Document": "07",
            "IDENTITY DOCUMENT": "07",
            "identity document": "07",
            "National ID Card + Certified passport copy": "02",
            "National ID card with photo": "21",
            "Driver's License": "08",
            "Driver's licence": "08",
            "driver's license": "08",
            "Drivers License": "08",
            "DRIVERS LICENSE": "08",
            "DRIVER LICENSE": "08",
            "Driver License": "08",
            "driver license": "08",
            "DL": "08",
            "Refugee travel document": "09",
            "Red cross travel document": "10",
            "UN laissez-passer": "11",
            "Employment Authorization": "06",
            "EMPLOYMENT AUTHORIZATION": "06",
            "Employment Authorization Card": "06",
            "EAD": "06",
            "Other": "06",
            "OTHER": "06",
        },
    },
    # Issuing country - standard HTML select
    # This field requires special handling based on ID type:
    # - Driver's License, Employment Authorization -> USA
    # - Passport, Consular ID -> Country of Birth
    "issuing_country": {
        "selector": "#_0e0ch0b1a0a0c1_input",
        "type": "html_select",
        "special_handler": "issuing_country",  # Flag for special handling in _fill_page
    },
}

# US State abbreviation to eMedical state code mapping
STATE_CODE_MAP = {
    "AL": "13", "AK": "14", "AZ": "15", "AR": "16", "CA": "17",
    "CO": "18", "CT": "19", "DE": "20", "DC": "21", "FL": "22",
    "GA": "23", "HI": "24", "ID": "25", "IL": "26", "IN": "27",
    "IA": "28", "KS": "29", "KY": "30", "LA": "31", "ME": "32",
    "MD": "33", "MA": "34", "MI": "35", "MN": "36", "MS": "37",
    "MO": "38", "MT": "39", "NE": "40", "NV": "41", "NH": "42",
    "NJ": "43", "NM": "44", "NY": "45", "NC": "46", "ND": "47",
    "OH": "48", "OK": "49", "OR": "50", "PA": "51", "RI": "52",
    "SC": "53", "SD": "54", "TN": "55", "TX": "56", "UT": "57",
    "VT": "58", "VA": "59", "WA": "60", "WV": "61", "WI": "62",
    "WY": "63", "AS": "AS", "GU": "GU", "MP": "MP", "PR": "PR",
    "VI": "VI", "FM": "FM", "MH": "MH", "PW": "PW",
    # Full state names as fallback
    "alabama": "13", "alaska": "14", "arizona": "15", "arkansas": "16",
    "california": "17", "colorado": "18", "connecticut": "19", "delaware": "20",
    "district of columbia": "21", "florida": "22", "georgia": "23", "hawaii": "24",
    "idaho": "25", "illinois": "26", "indiana": "27", "iowa": "28",
    "kansas": "29", "kentucky": "30", "louisiana": "31", "maine": "32",
    "maryland": "33", "massachusetts": "34", "michigan": "35", "minnesota": "36",
    "mississippi": "37", "missouri": "38", "montana": "39", "nebraska": "40",
    "nevada": "41", "new hampshire": "42", "new jersey": "43", "new mexico": "44",
    "new york": "45", "north carolina": "46", "north dakota": "47", "ohio": "48",
    "oklahoma": "49", "oregon": "50", "pennsylvania": "51", "rhode island": "52",
    "south carolina": "53", "south dakota": "54", "tennessee": "55", "texas": "56",
    "utah": "57", "vermont": "58", "virginia": "59", "washington": "60",
    "west virginia": "61", "wisconsin": "62", "wyoming": "63",
}


def get_state_code(state: str) -> str:
    """Convert state abbreviation or name to eMedical state code."""
    if not state:
        return ""
    # Try exact match first (for abbreviations like CA, NY)
    if state.upper() in STATE_CODE_MAP:
        return STATE_CODE_MAP[state.upper()]
    # Try lowercase full name
    normalized = state.lower().strip()
    return STATE_CODE_MAP.get(normalized, "")


# Page 3: Contact details - requires clicking add button and filling popup
PAGE3_FIELDS = {
    # Page 3 has a special flow: click add button -> popup -> fill fields -> close
    # This is handled specially in emedical.py, not through regular field filling
}

# Page 3 Address Popup selectors
PAGE3_ADDRESS_POPUP = {
    "add_button": "#pre_exam-health_case_details-_0j1a0",  # The Add New button to open popup
    "channel_type_dropdown": "#pre_exam-health_case_details-_0j1c-dlg-_0b0a1_input",
    "channel_type_value": "3",  # "Address (Home)"
    "country_dropdown": "#pre_exam-health_case_details-_0j1c-dlg-_0b1c0a0a1_input",
    "street_input": "#pre_exam-health_case_details-_0j1c-dlg-_0b1c0a0b1_input",
    "unit_input": "#pre_exam-health_case_details-_0j1c-dlg-_0b1c0a0c1_input",
    "city_input": "#pre_exam-health_case_details-_0j1c-dlg-_0b1c0a0f1_input",
    "state_dropdown": "#pre_exam-health_case_details-_0j1c-dlg-_0b1c0a0g1_input",
    "zip_input": "#pre_exam-health_case_details-_0j1c-dlg-_0b1c0a0i1_input",
    "save_button": "#pre_exam-health_case_details-_0j1c-dlg-_0b1g1",  # Save button in popup
}

# Page 3 Mobile Phone Popup selectors
PAGE3_PHONE_POPUP = {
    "add_button": "#pre_exam-health_case_details-_0j1a0",  # Add New button (after first save)
    "channel_type_dropdown": "#pre_exam-health_case_details-_0j1c-dlg-_0b0a1_input",
    "channel_type_value": "9",  # "Mobile (Personal)"
    "country_code_input": "#pre_exam-health_case_details-_0j1c-dlg-_0b1d0a0a1b2_input",
    "phone_input": "#pre_exam-health_case_details-_0j1c-dlg-_0b1d0a0a1b3_input",
    "save_button": "#pre_exam-health_case_details-_0j1c-dlg-_0b1g1",  # Same save button
}

# Page 4: Click Next to continue (no fields to fill)
PAGE4_FIELDS = {
    # Usually read-only summary
}

# Page 5: Identity Confirmation
PAGE5_IDENTITY = {
    "identity_doc_provided_yes": "input[name='pre_exam-confirm_identity-original_passport_presented'][value='2']",  # Radio: Yes
    "identity_concerns_no": "input[name='pre_exam-confirm_identity-any_id_concerns'][value='3']",  # Radio: No
    # ID Document Type dropdown (correct Page 5 selector)
    "id_doc_type_dropdown": "#pre_exam-confirm_identity-id_doc_presented_input",
    # Issuing Country dropdown (correct Page 5 selector)
    "issuing_country_dropdown": "#pre_exam-confirm_identity-issuing_country_input",
    # Other ID document text field (appears when "Other" is selected)
    "other_id_doc_input": "#pre_exam-confirm_identity-other_id_doc_input",
}

# ID Document Type mapping: I-693 Part 5.1 values -> eMedical dropdown values
PAGE5_ID_TYPE_MAP = {
    "passport": "01",           # Original Passport
    "pass": "01",               # Passport abbreviation
    "driver's license": "08",   # Driver's licence
    "drivers license": "08",    # Driver's licence (no apostrophe)
    "driver license": "08",     # Driver's licence
    "dl": "08",                 # Driver's license abbreviation
    "employment authorization": "06",  # Other (no direct match)
    "employment authorization card": "06",  # Other
    "ead": "06",                # Employment Authorization Document -> Other
    "consular id": "06",        # Other (no direct match, but uses country of birth)
    "consular id card": "06",   # Other
    "national id card": "07",   # National ID card
    "national id": "07",        # National ID card
    "identity document": "07",  # National ID card (I-693 uses "IDENTITY DOCUMENT - <COUNTRY>")
    "other": "06",              # Other
}

# Issuing Country mapping: Country names -> ISO 3-letter codes for Page 5 dropdown
# This is different from other country code mappings because Page 5 uses ISO 3166-1 alpha-3
# Comprehensive list matching all eMedical dropdown countries plus common alternatives
PAGE5_ISSUING_COUNTRY_MAP = {
    # A
    "afghanistan": "AFG",
    "albania": "ALB",
    "algeria": "DZA",
    "american samoa": "ASM",
    "andorra": "AND",
    "angola": "AGO",
    "anguilla": "AIA",
    "antarctica": "ATA",
    "antigua and barbuda": "ATG",
    "antigua": "ATG",
    "argentina": "ARG",
    "armenia": "ARM",
    "aruba": "ABW",
    "australia": "AUS",
    "austria": "AUT",
    "azerbaijan": "AZE",
    # B
    "bahamas": "BHS",
    "the bahamas": "BHS",
    "bahrain": "BHR",
    "bangladesh": "BGD",
    "barbados": "BRB",
    "belarus": "BLR",
    "belgium": "BEL",
    "belize": "BLZ",
    "benin": "BEN",
    "bermuda": "BMU",
    "bhutan": "BTN",
    "bolivia": "BOL",
    "bonaire": "BES",
    "bonaire, sint eustatius and saba": "BES",
    "bosnia": "BIH",
    "bosnia and herzegovina": "BIH",
    "bosnia & herzegovina": "BIH",
    "botswana": "BWA",
    "brazil": "BRA",
    "brasil": "BRA",
    "british indian ocean territory": "IOT",
    "brunei": "BRN",
    "brunei darussalam": "BRN",
    "bulgaria": "BGR",
    "burkina faso": "BFA",
    "burma": "BUR",
    "myanmar": "MMR",
    "burundi": "BDI",
    # C
    "cabo verde": "CPV",
    "cape verde": "CPV",
    "cambodia": "KHM",
    "cameroon": "CMR",
    "canada": "CAN",
    "cayman islands": "CYM",
    "central african republic": "CAF",
    "central african rep": "CAF",
    "chad": "TCD",
    "chile": "CHL",
    "china": "CHN",
    "china, peoples republic of": "CHN",
    "peoples republic of china": "CHN",
    "people's republic of china": "CHN",
    "prc": "CHN",
    "christmas island": "CXR",
    "cocos islands": "CCK",
    "cocos (keeling) islands": "CCK",
    "colombia": "COL",
    "comoros": "COM",
    "congo": "COG",
    "republic of the congo": "COG",
    "congo, republic of": "COG",
    "republic of congo": "COG",
    "democratic republic of the congo": "COD",
    "democratic republic of congo": "COD",
    "congo, dem republic": "COD",
    "dem rep of the congo": "COD",
    "dem rep of congo": "COD",
    "drc": "COD",
    "cook islands": "COK",
    "costa rica": "CRI",
    "cote d'ivoire": "CIV",
    "cote divoire": "CIV",
    "ivory coast": "CIV",
    "croatia": "HRV",
    "cuba": "CUB",
    "curacao": "CUW",
    "cyprus": "CYP",
    "czech republic": "CZE",
    "czechia": "CZE",
    "czechoslovakia": "CSK",
    # D
    "denmark": "DNK",
    "djibouti": "DJI",
    "dominica": "DMA",
    "dominican republic": "DOM",
    # E
    "ecuador": "ECU",
    "egypt": "EGY",
    "el salvador": "SLV",
    "equatorial guinea": "GNQ",
    "eritrea": "ERI",
    "estonia": "EST",
    "eswatini": "SWZ",
    "swaziland": "SWZ",
    "ethiopia": "ETH",
    # F
    "falkland islands": "FLK",
    "faroe islands": "FRO",
    "fiji": "FJI",
    "finland": "FIN",
    "france": "FRA",
    "french guiana": "GUF",
    "french polynesia": "PYF",
    # G
    "gabon": "GAB",
    "gambia": "GMB",
    "the gambia": "GMB",
    "georgia": "GEO",
    "germany": "D",
    "ghana": "GHA",
    "gibraltar": "GIB",
    "greece": "GRC",
    "greenland": "GRL",
    "grenada": "GRD",
    "guadeloupe": "GLP",
    "guam": "GUM",
    "guatemala": "GTM",
    "guernsey": "GGY",
    "guinea": "GIN",
    "guinea-bissau": "GNB",
    "guinea bissau": "GNB",
    "guyana": "GUY",
    # H
    "haiti": "HTI",
    "hong kong": "HKG",
    "hksar": "HKG",
    "hksar of the prc": "HKG",
    "honduras": "HND",
    "hungary": "HUN",
    # I
    "iceland": "ISL",
    "india": "IND",
    "indonesia": "IDN",
    "iran": "IRN",
    "islamic republic of iran": "IRN",
    "iraq": "IRQ",
    "ireland": "IRL",
    "isle of man": "IMN",
    "israel": "ISR",
    "italy": "ITA",
    # J
    "jamaica": "JAM",
    "japan": "JPN",
    "jersey": "JEY",
    "jordan": "JOR",
    # K
    "kazakhstan": "KAZ",
    "kenya": "KEN",
    "kiribati": "KIR",
    "korea, north": "PRK",
    "north korea": "PRK",
    "dprk": "PRK",
    "korea, south": "KOR",
    "south korea": "KOR",
    "korea": "KOR",
    "republic of korea": "KOR",
    "kosovo": "XKX",
    "kuwait": "KWT",
    "kyrgyzstan": "KGZ",
    # L
    "laos": "LAO",
    "lao": "LAO",
    "lao peoples dem rep": "LAO",
    "lao people's democratic republic": "LAO",
    "latvia": "LVA",
    "lebanon": "LBN",
    "lesotho": "LSO",
    "liberia": "LBR",
    "libya": "LBY",
    "liechtenstein": "LIE",
    "lithuania": "LTU",
    "luxembourg": "LUX",
    # M
    "macau": "MAC",
    "macao": "MAC",
    "madagascar": "MDG",
    "malawi": "MWI",
    "malaysia": "MYS",
    "maldives": "MDV",
    "mali": "MLI",
    "malta": "MLT",
    "marshall islands": "MHL",
    "martinique": "MTQ",
    "mauritania": "MRT",
    "mauritius": "MUS",
    "mayotte": "MYT",
    "mexico": "MEX",
    "micronesia": "FSM",
    "federated states of micronesia": "FSM",
    "moldova": "MDA",
    "monaco": "MCO",
    "mongolia": "MNG",
    "montenegro": "MNE",
    "montserrat": "MSR",
    "morocco": "MAR",
    "mozambique": "MOZ",
    # N
    "namibia": "NAM",
    "nauru": "NRU",
    "nepal": "NPL",
    "netherlands": "NLD",
    "holland": "NLD",
    "the netherlands": "NLD",
    "netherlands antilles": "ANT",
    "new caledonia": "NCL",
    "new zealand": "NZL",
    "nicaragua": "NIC",
    "niger": "NER",
    "nigeria": "NGA",
    "niue": "NIU",
    "norfolk island": "NFK",
    "north macedonia": "MKD",
    "macedonia": "MKD",
    "fyr macedonia": "MKD",
    "republic of north macedonia": "MKD",
    "northern mariana islands": "MNP",
    "norway": "NOR",
    # O
    "oman": "OMN",
    # P
    "pakistan": "PAK",
    "palau": "PLW",
    "palestine": "PSE",
    "palestine, state of": "PSE",
    "state of palestine": "PSE",
    "palestinian authority": "PSE",
    "panama": "PAN",
    "papua new guinea": "PNG",
    "png": "PNG",
    "paraguay": "PRY",
    "peru": "PER",
    "philippines": "PHL",
    "the philippines": "PHL",
    "pitcairn": "PCN",
    "poland": "POL",
    "portugal": "PRT",
    "puerto rico": "PRI",
    # Q
    "qatar": "QAT",
    # R
    "reunion": "REU",
    "romania": "ROU",
    "russia": "RUS",
    "russian federation": "RUS",
    "rwanda": "RWA",
    # S
    "saint lucia": "LCA",
    "st lucia": "LCA",
    "st. lucia": "LCA",
    "samoa": "WSM",
    "san marino": "SMR",
    "sao tome and principe": "STP",
    "sao tome & principe": "STP",
    "saudi arabia": "SAU",
    "senegal": "SEN",
    "serbia": "SRB",
    "serbia and montenegro": "SCG",
    "serbia & montenegro": "SCG",
    "seychelles": "SYC",
    "sierra leone": "SLE",
    "singapore": "SGP",
    "sint maarten": "SXM",
    "sint maarten (dutch part)": "SXM",
    "slovakia": "SVK",
    "slovenia": "SVN",
    "solomon islands": "SLB",
    "somalia": "SOM",
    "south africa": "ZAF",
    "south sudan": "SSD",
    "spain": "ESP",
    "sri lanka": "LKA",
    "st barthelemy": "BLM",
    "saint barthelemy": "BLM",
    "st helena": "SHN",
    "saint helena": "SHN",
    "st kitts and nevis": "KNA",
    "saint kitts and nevis": "KNA",
    "st kitts": "KNA",
    "st martin": "MAF",
    "saint martin": "MAF",
    "st pierre and miquelon": "SPM",
    "st pierre & miquelon": "SPM",
    "saint pierre and miquelon": "SPM",
    "st vincent and the grenadines": "VCT",
    "st vincent": "VCT",
    "saint vincent": "VCT",
    "saint vincent and the grenadines": "VCT",
    "sudan": "SDN",
    "suriname": "SUR",
    "surinam": "SUR",
    "svalbard": "SJM",
    "svalbard and jan mayen": "SJM",
    "sweden": "SWE",
    "switzerland": "CHE",
    "syria": "SYR",
    "syrian arab republic": "SYR",
    # T
    "taiwan": "TWN",
    "tajikistan": "TJK",
    "tanzania": "TZA",
    "thailand": "THA",
    "timor-leste": "TLS",
    "timor leste": "TLS",
    "east timor": "TLS",
    "togo": "TGO",
    "tokelau": "TKL",
    "tonga": "TON",
    "trinidad and tobago": "TTO",
    "trinidad": "TTO",
    "trinidad & tobago": "TTO",
    "tunisia": "TUN",
    "turkey": "TUR",
    "turkiye": "TUR",
    "turkmenistan": "TKM",
    "turks and caicos islands": "TCA",
    "turks and caicos": "TCA",
    "tuvalu": "TUV",
    # U
    "ussr": "SUN",
    "u.s.s.r.": "SUN",
    "soviet union": "SUN",
    "uganda": "UGA",
    "ukraine": "UKR",
    "united arab emirates": "ARE",
    "uae": "ARE",
    "united kingdom": "GBR",
    "uk": "GBR",
    "england": "GBR",
    "great britain": "GBR",
    "britain": "GBR",
    "scotland": "GBR",
    "wales": "GBR",
    "northern ireland": "GBR",
    "united states": "USA",
    "united states of america": "USA",
    "usa": "USA",
    "us": "USA",
    "unknown": "XXX",
    "uruguay": "URY",
    "uzbekistan": "UZB",
    # V
    "vanuatu": "VUT",
    "vatican city": "VAT",
    "vatican": "VAT",
    "vatican city state": "VAT",
    "holy see": "VAT",
    "venezuela": "VEN",
    "vietnam": "VNM",
    "viet nam": "VNM",
    "virgin islands (u.s)": "VIR",
    "virgin islands": "VIR",
    "us virgin islands": "VIR",
    "u.s. virgin islands": "VIR",
    "british virgin islands": "VGB",
    "virgin islands (british)": "VGB",
    # W
    "wallis and futuna": "WLF",
    "wallis & futuna": "WLF",
    "western sahara": "ESH",
    # Y
    "yemen": "YEM",
    "yemen, republic of": "YEM",
    "republic of yemen": "YEM",
    "yugoslavia": "YUG",
    # Z
    "zaire": "ZAR",
    "zambia": "ZMB",
    "zimbabwe": "ZWE",
}


def get_page5_id_type_code(id_type: str) -> str:
    """Convert I-693 Part 5.1 ID type to eMedical dropdown value.
    
    Uses keyword matching so that state-prefixed entries like
    "TEXAS DRIVER LICENSE" are correctly recognised as Driver's licence (08).
    """
    if not id_type:
        return "06"  # Default to Other
    normalized = id_type.lower().strip()

    # 1. Try exact match first (cheap)
    exact = PAGE5_ID_TYPE_MAP.get(normalized)
    if exact is not None:
        return exact

    # 2. Keyword / substring matching (order matters: most specific first)
    # Driver's licence variants (may be prefixed with a US state name)
    if any(kw in normalized for kw in ["driver", "license", "licence", " dl", "dl "]):
        return "08"

    # Passport
    if "passport" in normalized:
        return "01"

    # National ID / Identity Document
    if any(kw in normalized for kw in ["national id", "identity document"]):
        return "07"

    # Employment authorization
    if any(kw in normalized for kw in ["employment", "authorization", "ead"]):
        return "06"

    # Consular ID
    if "consular" in normalized:
        return "06"

    # Refugee travel document
    if "refugee" in normalized:
        return "09"

    # Default to Other
    return "06"


def get_page5_issuing_country(id_type: str, country_of_birth: str, id_issuing_country: str = "") -> str:
    """
    Determine issuing country based on ID type, country of birth, and
    the explicitly-parsed issuing country from the I-693 form.
    
    Priority:
    0. If id_issuing_country was parsed from the I-693 (e.g. "CONSULAR ID CARD - MEXICO"),
       use it directly - this is the most reliable source.
    
    Rules (when no explicit issuing country parsed):
    1. Passport -> Country of Birth
    2. Driver's License -> United States
    3. Employment Authorization -> United States
    4. Consular ID Card -> Country of Birth
    5. Other -> Country of Birth (default)
    """
    # If the parser extracted an explicit issuing country, use it directly
    if id_issuing_country:
        normalized = id_issuing_country.lower().strip()
        code = PAGE5_ISSUING_COUNTRY_MAP.get(normalized, "")
        if code:
            print(f"DEBUG: Using parsed issuing country: '{id_issuing_country}' -> '{code}'")
            return code
        print(f"DEBUG: Parsed issuing country '{id_issuing_country}' not in map, falling through to rules")
    
    if not id_type:
        return "USA"  # Default
    
    normalized_id = id_type.lower().strip()
    
    # Consular ID -> Country of Birth  (check BEFORE generic "id card" rule)
    if "consular" in normalized_id:
        if country_of_birth:
            normalized_country = country_of_birth.lower().strip()
            return PAGE5_ISSUING_COUNTRY_MAP.get(normalized_country, "XXX")
        return "XXX"
    
    # Driver's License, Employment Authorization -> USA
    if any(x in normalized_id for x in ["driver", "license", "licence", "dl", "employment", "authorization", "ead"]):
        return "USA"
    
    # Passport -> Country of Birth
    if any(x in normalized_id for x in ["passport", "pass"]):
        if country_of_birth:
            normalized_country = country_of_birth.lower().strip()
            return PAGE5_ISSUING_COUNTRY_MAP.get(normalized_country, "XXX")
        return "XXX"
    
    # Default: use country of birth if available
    if country_of_birth:
        normalized_country = country_of_birth.lower().strip()
        return PAGE5_ISSUING_COUNTRY_MAP.get(normalized_country, "XXX")
    
    return "USA"  # Final fallback

# File upload selectors on Page 9
PAGE9_FILE_UPLOADS = {
    "add_new_button": "#hr513-_2a0b0a0bj1b1a1a0b",  # "Add New" button to open upload popup
    "document_type_dropdown": "#hr513-_2a0b0a0bj1b1a1a0-dlg-_0a1c1_input",  # Document type dropdown
    "file_input": "#hr513-_2a0b0a0bj1b1a1a0-dlg-_0a1e1_input",  # File input element
    "description_textarea": "#hr513-_2a0b0a0bj1b1a1a0-dlg-_0a1f1_input",  # Description textarea (for "Other" type)
    "save_button": "#hr513-_2a0b0a0bj1b1a1a0-dlg-_0a4b",  # Save button to close popup after upload
    "document_types": {
        "i693": "RIMEVR",           # I-693 form
        "chest_xray": "OTHR",        # Chest x-ray REPORT (not DICOM image) - use "Other" category
        "lab_results": "TIRPT",      # TST/IGRA test report (lab results)
        "other": "OTHR",             # Other
    },
    # Wait times for upload to complete (seconds)
    # These are minimum waits after triggering the upload; the save-button
    # enable check (timeout=120s) provides the real upper-bound safety net.
    "wait_times": {
        "i693": 20,           # I-693 form - largest file, wait longer
        "lab_results": 5,     # TST/IGRA test report - smaller file
        "chest_xray": 5,      # Chest x-ray report - smaller file
    },
    # Description text for "Other" document type
    "descriptions": {
        "chest_xray": "CHEST X-RAY REPORT",  # Required description for chest x-ray report
    },
}

# Legacy file upload config (for reference)
FILE_UPLOADS = {
    "lab_results": {
        "selector": "#labResultsUpload",  # UPDATE with actual selector
        "type": "file",
    },
    "chest_xray": {
        "selector": "#chestXrayUpload",  # UPDATE with actual selector  
        "type": "file",
    },
}

# Page 6 - Start Exams page
PAGE6_START_EXAMS = {
    "start_exams_button": "#_0e0bi0a1a0a2a2b3",  # "Start Exam(s)" button
}

# Page 7 - Selective History and TB section
PAGE7_SELECTIVE_TB = {
    "selective_tb_section": "summary:has(#_0e0bi0a1a0a2a1a1b0a0a)",  # "Selective History and TB" expandable section
}

# Page 8 - View Exam button
PAGE8_VIEW_EXAM = {
    "view_exam_button": "#_0e0bi0a1a0a2a1a1b0a0b9f",  # "View exam" button
}

# Page 9 - Exam date and IGRA test entry
PAGE9_EXAM_DATE = {
    "exam_date_input": "#hr513-_2a0b0a0a1a0a1a0_input",  # Exam date field (DD MMM YYYY format)
    "igra_radio": "input[name='hr513-_2a0b0a0be1a1'][value='IGRA']",  # IGRA radio button
    "igra_test_dropdown": "#hr513-_2a0b0a0be2a1_input",  # IGRA test type dropdown
    "igra_test_values": {
        "Quantiferon": "QNTFN",
        "QF": "QNTFN",
        "QUANTIFERON": "QNTFN",
        "T-Spot": "TSPOT",
        "TSPOT": "TSPOT",
    },
    "igra_date_input": "#hr513-_2a0b0a0be2b1_input",  # IGRA blood sample date
    "igra_result_radio_name": "hr513-_2a0b0a0be2c1",  # IGRA result radio button group
    "igra_result_values": {
        # I-693 Part 8.1.A(1) result → eMedical radio value
        "N": "NGTV",      # Negative
        "P": "PSTV",      # Positive
        "I": "INDT",      # Indeterminate
        "Negative": "NGTV",
        "Positive": "PSTV",
        "Indeterminate": "INDT",
    },
    # Chest X-ray requirement radio (Part 8.1.A(2))
    "chest_xray_req_radio_name": "hr513-_2a0b0a0bf1a1",
    "chest_xray_req_values": {
        "N_REQ": "N_REQ",   # Chest x-ray not required (medically cleared for TB)
        "REQ": "REQ",       # Required
    },
    # Chest X-ray reason checkboxes (Part 8.1.A(2) - why X-ray was required)
    "xray_reason_initial_screening": "#hr513-_2a0b0a0bf2b0b_input",  # Initial screening results (Positive IGRA/TST)
    "xray_reason_tb_signs": "#hr513-_2a0b0a0bf2b1b_input",  # TB signs/symptoms or immunosuppression
    "xray_reason_igra_exception": "#hr513-_2a0b0a0bf2b2b_input",  # IGRA exception
    # Chest X-ray read date (Part 8.1.A(3))
    "xray_read_date_input": "#hr513-_2a0b0a0bf2b3b_input",
    # Chest X-ray result radio button (Part 8.1.A(3))
    "xray_result_radio_name": "hr513-_2a0b0a0bf2b4b",
    "xray_result_values": {
        "N": "NRM",   # Normal
        "A": "ABN",   # Abnormal findings suggestive of TB
    },
    # Chest X-ray abnormal findings checkboxes (appear after selecting ABN)
    # Maps I-693 model field name → eMedical checkbox selector
    "xray_abnormal_findings": {
        "xray_infiltrate":      "#hr513-_2a0b0a0bf2c1a1_input",   # Infiltrate or consolidation
        "xray_reticular":       "#hr513-_2a0b0a0bf2c1b1_input",   # Reticular markings suggestive of fibrosis
        "xray_cavity":          "#hr513-_2a0b0a0bf2c1c1_input",   # Cavitary lesion
        "xray_nodules":         "#hr513-_2a0b0a0bf2c1d1_input",   # Nodule or mass with poorly defined margins
        "xray_pleural":         "#hr513-_2a0b0a0bf2c1e1_input",   # Pleural effusion
        "xray_hilar":           "#hr513-_2a0b0a0bf2c1f1_input",   # Hilar / mediastinal adenopathy
        "xray_miliary":         "#hr513-_2a0b0a0bf2c1g1_input",   # Miliary findings
        "xray_linear":          "#hr513-_2a0b0a0bf2c1h1_input",   # Discrete linear opacity
        "xray_discrete_nodule": "#hr513-_2a0b0a0bf2c1i1_input",   # Discrete nodule(s) without calcification
        "xray_volume_loss":     "#hr513-_2a0b0a0bf2c1j1_input",   # Volume loss or retraction
        "xray_thick_pleural":   "#hr513-_2a0b0a0bf2c1ba1_input",  # Irregular thick pleural reaction
        "xray_other":           "#hr513-_2a0b0a0bf2c1bb1_input",  # Other
    },
    # Sputum smears radio button (Part 8.1.A(4))
    "sputum_radio_name": "hr513-_2a0b0a0bg1a1",
    "sputum_values": {
        "NI": "NI",   # Not indicated
        "IND": "IND", # Indicated
    },
    # Sputum reason checkboxes (shown after selecting "Indicated")
    "sputum_reason_signs_symptoms": "#hr513-_2a0b0a0bg2b0b_input",  # Signs or symptoms of TB
    "sputum_reason_chest_xray": "#hr513-_2a0b0a0bg2b1b_input",      # Chest X-ray suggestive of TB
    "sputum_reason_hiv_extrapulm": "#hr513-_2a0b0a0bg2b2b_input",   # HIV infection or extrapulmonary TB
    "sputum_reason_end_treatment": "#hr513-_2a0b0a0bg2b3b_input",   # End of treatment cultures
    # Sputum Smear Results (Part 8.1.A(5)(a)) - 3 rows
    # Each row: specimen date, result date, result dropdown (POS/NEG)
    "sputum_smear_rows": [
        {
            "specimen_date": "#hr513-_2a0b0a0bg2c1a0d_input",
            "result_date": "#hr513-_2a0b0a0bg2c1a0e_input",
            "result_dropdown": "#hr513-_2a0b0a0bg2c1a0f_input",
        },
        {
            "specimen_date": "#hr513-_2a0b0a0bg2c1a0g_input",
            "result_date": "#hr513-_2a0b0a0bg2c1a0h_input",
            "result_dropdown": "#hr513-_2a0b0a0bg2c1a0i_input",
        },
        {
            "specimen_date": "#hr513-_2a0b0a0bg2c1a0j_input",
            "result_date": "#hr513-_2a0b0a0bg2c1a0ba_input",
            "result_dropdown": "#hr513-_2a0b0a0bg2c1a0bb_input",
        },
    ],
    "sputum_smear_result_values": {
        "POS": "POS",
        "POSITIVE": "POS",
        "P": "POS",
        "NEG": "NEG",
        "NEGATIVE": "NEG",
        "N": "NEG",
    },
    # Sputum Culture Results (Part 8.1.A(5)(b)) - 3 rows
    # Each row: specimen date, result date, result dropdown (NEG/POS/NTM/CNTAMNTD)
    "sputum_culture_rows": [
        {
            "specimen_date": "#hr513-_2a0b0a0bg2d1a0d_input",
            "result_date": "#hr513-_2a0b0a0bg2d1a0e_input",
            "result_dropdown": "#hr513-_2a0b0a0bg2d1a0f_input",
        },
        {
            "specimen_date": "#hr513-_2a0b0a0bg2d1a0g_input",
            "result_date": "#hr513-_2a0b0a0bg2d1a0h_input",
            "result_dropdown": "#hr513-_2a0b0a0bg2d1a0i_input",
        },
        {
            "specimen_date": "#hr513-_2a0b0a0bg2d1a0j_input",
            "result_date": "#hr513-_2a0b0a0bg2d1a0ba_input",
            "result_dropdown": "#hr513-_2a0b0a0bg2d1a0bb_input",
        },
    ],
    "sputum_culture_result_values": {
        "POS": "POS",
        "POSITIVE": "POS",
        "P": "POS",
        "NEG": "NEG",
        "NEGATIVE": "NEG",
        "N": "NEG",
        "NTM": "NTM",
        "CNTAMNTD": "CNTAMNTD",
        "CONTAMINATED": "CNTAMNTD",
    },
    # TB Classification checkboxes (Part 8.1.A(6))
    "tb_classification_checkboxes": {
        "NO_TB": "#hr513-_2a0b0a0bh1a1_input",        # No Class A or Class B TB
        "CLASS_A": "#hr513-_2a0b0a0bh1b1_input",      # Class A Tuberculosis disease
        "B0_PULM": "#hr513-_2a0b0a0bh1c1_input",      # B0 TB, Pulmonary
        "B1_PULM": "#hr513-_2a0b0a0bh1d1_input",      # B1 TB, Pulmonary
        "B1_EXTRAPULM": "#hr513-_2a0b0a0bh1e1_input", # B1 TB, Extrapulmonary
        "B2_LTBI": "#hr513-_2a0b0a0bh1f1_input",      # B2 TB, LTBI Evaluation
        "B_OTHER": "#hr513-_2a0b0a0bh1g1_input",      # Class B, Other Chest Condition (Non-TB)
    },
    # TB Remarks textarea (I-693 Part 8 A.(7)) — discovered dynamically at runtime
    "remarks_textarea": "#hr513-_2a0b0a0bi1a1_input",
}

# Navigation button selectors
PAGE_NAVIGATION = {
    "username_field": "input[type='text']",  # From discovered_selectors.json
    "password_field": "#logon-password_input",  # From discovered_selectors.json
    "login_button": "#logon-btnLogon",  # From discovered_selectors.json
    "page1_search_button": "#caseSearch-search",
    "page1_create_case": "#caseSearch-createCase",
    "page1_next": "#nextBtn",  # UPDATE when found
    "page2_next": "#_0e0ch0g1",  # "Create" button on page 2
    "page3_next": "#pre_exam-_2a0c1a",  # "Next" button on page 3
    "page4_next": "#pre_exam-_2b0c1a",  # "Next" button on page 4
    "page5_next": "#pre_exam-_2c0c1a",  # "Next" button on page 5
    "page6_start_exams": "#_0e0bi0a1a0a2a2b3",  # "Start Exam(s)" button on page 6
    "page3_ok_modal": ".modal-footer .btn-primary",  # If there's a confirmation modal
    "final_submit": "#submitBtn",  # DO NOT auto-click - user reviews first
}

# All pages combined for iteration
EMEDICAL_PAGES = {
    "page1": PAGE1_FIELDS,
    "page2": PAGE2_FIELDS,
    "page3": PAGE3_FIELDS,
    "page4": PAGE4_FIELDS,
}


def get_page_fields(page_number: int) -> dict:
    """Get field mapping for a specific page."""
    page_key = f"page{page_number}"
    return EMEDICAL_PAGES.get(page_key, {})


def get_navigation_selector(action: str) -> str:
    """Get selector for a navigation button."""
    return PAGE_NAVIGATION.get(action, "")
