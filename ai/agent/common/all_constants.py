"""
全交易所品种常量

包含 CFFEX / CZCE / DCE / GFEX / INE / SHFE 所有主要期货品种。
期权合约（含 C888/P888/-C-/-P-/数字+C/P）已排除，仅保留期货主连。

用法：
    from ai.agent.common.all_constants import ALL_VARIETIES, VARIETY_NAMES, EXCHANGE_VARIETIES
"""

# ─────────────────────────────────────────────────────────────────────────────
# CFFEX 中国金融期货交易所
# ─────────────────────────────────────────────────────────────────────────────
CFFEX_VARIETIES = ["IC", "IF", "IH", "IM", "T", "TF", "TL", "TS"]

CFFEX_VARIETY_NAMES = {
    "IC": "中证500",
    "IF": "沪深300",
    "IH": "上证50",
    "IM": "中证1000",
    "T":  "10年国债",
    "TF": "5年国债",
    "TL": "30年国债",
    "TS": "2年国债",
}

# ─────────────────────────────────────────────────────────────────────────────
# CZCE 郑州商品交易所
# ─────────────────────────────────────────────────────────────────────────────
CZCE_VARIETIES = [
    "AP", "CF", "CJ", "CY", "FG", "JR", "LR", "MA", "OI", "PF",
    "PK", "PL", "PM", "PR", "PX", "RI", "RM", "RS", "SA", "SF",
    "SH", "SM", "SR", "TA", "UR", "WH", "ZC",
]

CZCE_VARIETY_NAMES = {
    "AP": "苹果",
    "CF": "棉花",
    "CJ": "粳稻",
    "CY": "棉纱",
    "FG": "玻璃",
    "JR": "粳稻(旧)",
    "LR": "晚籼稻",
    "MA": "甲醇",
    "OI": "菜籽油",
    "PF": "短纤",
    "PK": "花生",
    "PL": "多晶硅",
    "PM": "普麦",
    "PR": "丙烯",
    "PX": "对二甲苯",
    "RI": "早籼稻",
    "RM": "菜粕",
    "RS": "油菜籽",
    "SA": "纯碱",
    "SF": "硅铁",
    "SH": "烧碱",
    "SM": "硅锰",
    "SR": "白糖",
    "TA": "PTA",
    "UR": "尿素",
    "WH": "强麦",
    "ZC": "动力煤",
}

# ─────────────────────────────────────────────────────────────────────────────
# DCE 大连商品交易所
# ─────────────────────────────────────────────────────────────────────────────
DCE_VARIETIES = [
    "a", "b", "bb", "bz", "c", "cs", "eb", "eg", "fb", "i",
    "j", "jd", "jm", "l", "lg", "lh", "m", "p", "pg", "pp",
    "rr", "v", "y",
]

DCE_VARIETY_NAMES = {
    "a":  "豆一",
    "b":  "豆二",
    "bb": "胶合板",
    "bz": "苯乙烯(新)",
    "c":  "玉米",
    "cs": "玉米淀粉",
    "eb": "苯乙烯",
    "eg": "乙二醇",
    "fb": "纤维板",
    "i":  "铁矿石",
    "j":  "焦炭",
    "jd": "鸡蛋",
    "jm": "焦煤",
    "l":  "塑料",
    "lg": "液化石油气(lg)",
    "lh": "生猪",
    "m":  "豆粕",
    "p":  "棕榈油",
    "pg": "液化石油气",
    "pp": "聚丙烯",
    "rr": "粳米",
    "v":  "PVC",
    "y":  "豆油",
}

# ─────────────────────────────────────────────────────────────────────────────
# GFEX 广州期货交易所
# ─────────────────────────────────────────────────────────────────────────────
GFEX_VARIETIES = ["lc", "pd", "ps", "pt", "si"]

GFEX_VARIETY_NAMES = {
    "lc": "碳酸锂",
    "pd": "钯",
    "ps": "多晶硅(ps)",
    "pt": "铂",
    "si": "工业硅",
}

# ─────────────────────────────────────────────────────────────────────────────
# INE 上海国际能源交易中心
# ─────────────────────────────────────────────────────────────────────────────
INE_VARIETIES = ["bc", "ec", "lu", "nr", "sc"]

INE_VARIETY_NAMES = {
    "bc": "国际铜",
    "ec": "欧线集运",
    "lu": "低硫燃料油",
    "nr": "20号胶",
    "sc": "原油",
}

# ─────────────────────────────────────────────────────────────────────────────
# SHFE 上海期货交易所
# ─────────────────────────────────────────────────────────────────────────────
SHFE_VARIETIES = [
    "ad", "ag", "al", "ao", "au", "br", "bu", "cu", "fu",
    "hc", "ni", "op", "pb", "rb", "ru", "sn", "sp", "ss", "wr", "zn",
]

SHFE_VARIETY_NAMES = {
    "ad": "氧化铝",
    "ag": "白银",
    "al": "铝",
    "ao": "氧化铝(ao)",
    "au": "黄金",
    "br": "丁二烯橡胶",
    "bu": "沥青",
    "cu": "铜",
    "fu": "燃料油",
    "hc": "热卷",
    "ni": "镍",
    "op": "纸浆(op)",
    "pb": "铅",
    "rb": "螺纹钢",
    "ru": "橡胶",
    "sn": "锡",
    "sp": "纸浆",
    "ss": "不锈钢",
    "wr": "线材",
    "zn": "锌",
}

# ─────────────────────────────────────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────────────────────────────────────

# 交易所 → (品种列表, 品种名称字典)
EXCHANGE_VARIETIES = {
    "CFFEX": (CFFEX_VARIETIES, CFFEX_VARIETY_NAMES),
    "CZCE":  (CZCE_VARIETIES,  CZCE_VARIETY_NAMES),
    "DCE":   (DCE_VARIETIES,   DCE_VARIETY_NAMES),
    "GFEX":  (GFEX_VARIETIES,  GFEX_VARIETY_NAMES),
    "INE":   (INE_VARIETIES,   INE_VARIETY_NAMES),
    "SHFE":  (SHFE_VARIETIES,  SHFE_VARIETY_NAMES),
}

# 交易所中文名
EXCHANGE_CN_NAMES = {
    "CFFEX": "中金所",
    "CZCE":  "郑商所",
    "DCE":   "大商所",
    "GFEX":  "广期所",
    "INE":   "上期能源",
    "SHFE":  "上期所",
}

# 全量品种名称字典（所有交易所合并）
VARIETY_NAMES: dict = {}
for _varieties, _names in EXCHANGE_VARIETIES.values():
    VARIETY_NAMES.update(_names)

# 全量品种列表（所有交易所合并，带 exchange 标注）
ALL_VARIETIES: list = []  # [(exchange, variety), ...]
for _exchange, (_varieties, _) in EXCHANGE_VARIETIES.items():
    for _v in _varieties:
        ALL_VARIETIES.append((_exchange, _v))
