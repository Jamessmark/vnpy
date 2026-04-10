"""
配置文件：品种、LLM 参数
"""

from pathlib import Path

# ── 项目根目录 ─────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent.parent  # vnpy/

# ── 监控品种配置 ───────────────────────────────────────────────────
# 只纳入有完整历史日K（1514根，2020年起）的 CZCE 主连合约
# 格式：(symbol, exchange_value, 中文名称, product_prefix, product_exchange)
WATCH_SYMBOLS = [
    # ── 郑商所（CZCE）── 有完整历史日K（2020年起）────────────────
    ("AP888", "LOCAL", "苹果",       "AP", "CZCE"),
    ("CF888", "LOCAL", "棉花",       "CF", "CZCE"),
    ("CJ888", "LOCAL", "粳米",       "CJ", "CZCE"),
    ("CY888", "LOCAL", "棉纱",       "CY", "CZCE"),
    ("FG888", "LOCAL", "玻璃",       "FG", "CZCE"),
    ("MA888", "LOCAL", "甲醇",       "MA", "CZCE"),
    ("OI888", "LOCAL", "菜油",       "OI", "CZCE"),
    ("PF888", "LOCAL", "短纤",       "PF", "CZCE"),
    ("PK888", "LOCAL", "花生",       "PK", "CZCE"),
    ("RM888", "LOCAL", "菜粕",       "RM", "CZCE"),
    ("RS888", "LOCAL", "菜籽",       "RS", "CZCE"),
    ("SA888", "LOCAL", "纯碱",       "SA", "CZCE"),
    ("SF888", "LOCAL", "硅铁",       "SF", "CZCE"),
    ("SM888", "LOCAL", "锰硅",       "SM", "CZCE"),
    ("SR888", "LOCAL", "白糖",       "SR", "CZCE"),
    ("TA888", "LOCAL", "PTA",        "TA", "CZCE"),
    ("UR888", "LOCAL", "尿素",       "UR", "CZCE"),
    ("ZC888", "LOCAL", "动力煤",     "ZC", "CZCE"),
    # ── 大商所（DCE）── 近期数据（2026年4月起）────────────────────
    ("a888",  "LOCAL", "豆一",       "a",  "DCE"),
    ("b888",  "LOCAL", "豆二",       "b",  "DCE"),
    ("bb888", "LOCAL", "细木工板",   "bb", "DCE"),
    ("bz888", "LOCAL", "苯乙烯",     "bz", "DCE"),
    ("c888",  "LOCAL", "玉米",       "c",  "DCE"),
    ("cs888", "LOCAL", "淀粉",       "cs", "DCE"),
    ("eb888", "LOCAL", "苯乙烯(eb)", "eb", "DCE"),
    ("eg888", "LOCAL", "乙二醇",     "eg", "DCE"),
    ("fb888", "LOCAL", "纤维板",     "fb", "DCE"),
    ("i888",  "LOCAL", "铁矿石",     "i",  "DCE"),
    ("j888",  "LOCAL", "焦炭",       "j",  "DCE"),
    ("jd888", "LOCAL", "鸡蛋",       "jd", "DCE"),
    ("jm888", "LOCAL", "焦煤",       "jm", "DCE"),
    ("l888",  "LOCAL", "聚乙烯",     "l",  "DCE"),
    ("lg888", "LOCAL", "LPG",        "lg", "DCE"),
    ("lh888", "LOCAL", "生猪",       "lh", "DCE"),
    ("m888",  "LOCAL", "豆粕",       "m",  "DCE"),
    ("p888",  "LOCAL", "棕榈油",     "p",  "DCE"),
    ("pg888", "LOCAL", "LPG(pg)",    "pg", "DCE"),
    ("pp888", "LOCAL", "聚丙烯",     "pp", "DCE"),
    ("rr888", "LOCAL", "粳稻",       "rr", "DCE"),
    ("v888",  "LOCAL", "PVC",        "v",  "DCE"),
    ("y888",  "LOCAL", "豆油",       "y",  "DCE"),
    # ── 上期所（SHFE）── 近期数据 ─────────────────────────────────
    ("bu888", "LOCAL", "沥青",       "bu", "SHFE"),
    ("cu888", "LOCAL", "铜",         "cu", "SHFE"),
    ("fu888", "LOCAL", "燃料油",     "fu", "SHFE"),
    ("hc888", "LOCAL", "热轧卷板",   "hc", "SHFE"),
    ("ni888", "LOCAL", "镍",         "ni", "SHFE"),
    ("rb888", "LOCAL", "螺纹钢",     "rb", "SHFE"),
    ("ru888", "LOCAL", "橡胶",       "ru", "SHFE"),
    ("sp888", "LOCAL", "纸浆",       "sp", "SHFE"),
    ("ss888", "LOCAL", "不锈钢",     "ss", "SHFE"),
    ("wr888", "LOCAL", "线材",       "wr", "SHFE"),
    # ── 上期所贵金属 ──────────────────────────────────────────────
    ("ag888", "LOCAL", "白银",       "ag", "SHFE"),
    ("au888", "LOCAL", "黄金",       "au", "SHFE"),
    ("pb888", "LOCAL", "铅",         "pb", "SHFE"),
    ("sn888", "LOCAL", "锡",         "sn", "SHFE"),
    ("zn888", "LOCAL", "锌",         "zn", "SHFE"),
    # ── 上期所能源 ────────────────────────────────────────────────
    ("sc888", "LOCAL", "原油",       "sc", "SHFE"),
    ("lu888", "LOCAL", "低硫燃油",   "lu", "SHFE"),
    ("nr888", "LOCAL", "20号胶",     "nr", "SHFE"),
    ("br888", "LOCAL", "丁二烯橡胶", "br", "SHFE"),
    ("op888", "LOCAL", "期权标的",   "op", "SHFE"),
    # ── 中金所（CFFEX）── 股指期货 ───────────────────────────────
    ("IC888", "LOCAL", "中证500",    "IC", "CFFEX"),
    ("IF888", "LOCAL", "沪深300",    "IF", "CFFEX"),
    ("IH888", "LOCAL", "上证50",     "IH", "CFFEX"),
    ("IM888", "LOCAL", "中证1000",   "IM", "CFFEX"),
    # ── 中金所国债期货 ────────────────────────────────────────────
    ("T888",  "LOCAL", "10年国债",   "T",  "CFFEX"),
    ("TF888", "LOCAL", "5年国债",    "TF", "CFFEX"),
    ("TL888", "LOCAL", "30年国债",   "TL", "CFFEX"),
    ("TS888", "LOCAL", "2年国债",    "TS", "CFFEX"),
    # ── 广期所（GFEX）── 近期数据 ────────────────────────────────
    ("lc888", "LOCAL", "碳酸锂",     "lc", "GFEX"),
    ("pd888", "LOCAL", "工业硅",     "pd", "GFEX"),
    ("ps888", "LOCAL", "多晶硅",     "ps", "GFEX"),
    ("pt888", "LOCAL", "铂",         "pt", "GFEX"),
    ("si888", "LOCAL", "工业硅(si)", "si", "GFEX"),
    ("ec888", "LOCAL", "集运欧线",   "ec", "GFEX"),
]

# 历史数据天数（取最近 N 个交易日）
BAR_LOOKBACK_DAYS = 10   # 原 20，减少约 50% Token 消耗

# ── 报告输出目录 ───────────────────────────────────────────────────
REPORTS_DIR = Path(__file__).parent / "reports"

# ── 定时运行时间 ───────────────────────────────────────────────────
SCHEDULE_TIME = "17:00"   # 每天下午 17:00
