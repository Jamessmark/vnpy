"""
期货主连 MLP 量化研究：训练 + 回测完整流程

数据依赖：
    先运行  uv run python ai/data_process/prepare_futures_data.py
    确保 ai/data/lab/daily/ 下有 parquet 文件

运行方式：
    uv run python ai/train/futures_mlp_backtest.py

流程：
    Step 1  加载数据      AlphaLab.load_bar_df()
    Step 2  构建因子      Alpha158 计算 158 个价量因子
    Step 3  数据处理      截面归一化 / 去 NaN
    Step 4  训练模型      MLP（train / valid 早停）
    Step 5  生成信号      在 test 区间预测
    Step 6  回测          BacktestingEngine → 统计指标 + 净值图
"""

import sys
from pathlib import Path
from datetime import datetime

# 项目根目录（ai/train/ 的上两级）
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import polars as pl

from vnpy.trader.constant import Interval
from vnpy.alpha import AlphaLab
from vnpy.alpha.dataset import Segment
from vnpy.alpha.dataset.datasets.alpha_158 import Alpha158
from vnpy.alpha.dataset.processor import process_drop_na, process_cs_norm, process_cs_rank_norm
from vnpy.alpha.model.models.mlp_model import MlpModel
from vnpy.alpha.strategy.backtesting import BacktestingEngine
from functools import partial

# ─────────────────────────────────────────────────────────────────────────────
# ① 全局配置 — 按需修改
# ─────────────────────────────────────────────────────────────────────────────

# AlphaLab 数据目录
LAB_PATH = str(ROOT / "ai" / "data" / "lab")

# 回测品种：CZCE 主连（从 2020 年起有完整历史）
VT_SYMBOLS = [
    "AP888.LOCAL", "CF888.LOCAL", "CJ888.LOCAL", "CY888.LOCAL",
    "FG888.LOCAL", "MA888.LOCAL", "OI888.LOCAL", "PF888.LOCAL",
    "PK888.LOCAL", "RM888.LOCAL", "SA888.LOCAL", "SF888.LOCAL",
    "SM888.LOCAL", "SR888.LOCAL", "TA888.LOCAL", "UR888.LOCAL",
    "ZC888.LOCAL",
]

# 时间分段（train+valid 用于训练，test 用于回测）
TRAIN_PERIOD = ("2020-01-01", "2023-06-30")
VALID_PERIOD = ("2023-07-01", "2024-06-30")
TEST_PERIOD  = ("2024-07-01", "2026-04-01")

# 加载数据时额外往前取的天数（滚动指标预热期）
EXTENDED_DAYS = 120

# MLP 超参数
# 实验对比：
#   (256,128) 过拟合严重，valid早停@Step50，IC=0.014，Sharpe=0.52
#   (64,32)   轻微过拟合，valid停@Step180，IC=0.012，Sharpe=-0.006
#   (32,16)   欠拟合，容量不足表达158维特征间的非线性关系
#   (128,64)  ← 推荐：平衡点，配合 weight_decay=1e-4
MLP_PARAMS = dict(
    input_size=158,           # Alpha158 因子数
    hidden_sizes=(128, 64),   # 中等网络，平衡容量与过拟合
    n_epochs=300,
    early_stop_rounds=30,
    eval_steps=10,
    weight_decay=1e-4,        # L2 正则
    seed=42,
)

# 是否保存 dataset / model / signal 到 lab
SAVE_ARTIFACTS = True
ARTIFACT_NAME  = "futures_mlp_v1"

# ─────────────────────────────────────────────────────────────────────────────
# 期货合约参数（回测必须）
# 格式：vt_symbol -> (long_rate, short_rate, size, pricetick)
# ─────────────────────────────────────────────────────────────────────────────
CONTRACT_SETTINGS: dict[str, tuple] = {
    # 郑商所
    "AP888.LOCAL":  (3/10000,  3/10000,  10,   1.0),   # 苹果
    "CF888.LOCAL":  (3/10000,  3/10000,   5,   5.0),   # 棉花
    "CJ888.LOCAL":  (3/10000,  3/10000,   5,   5.0),   # 粳米
    "CY888.LOCAL":  (3/10000,  3/10000,   5,   5.0),   # 棉纱
    "FG888.LOCAL":  (1/10000,  1/10000,  20,   1.0),   # 玻璃
    "MA888.LOCAL":  (0.5/10000,0.5/10000, 10,  1.0),   # 甲醇
    "OI888.LOCAL":  (2/10000,  2/10000,  10,   2.0),   # 菜油
    "PF888.LOCAL":  (1/10000,  1/10000,   5,   2.0),   # 短纤
    "PK888.LOCAL":  (3/10000,  3/10000,   5,   2.0),   # 花生
    "RM888.LOCAL":  (1.5/10000,1.5/10000, 10,  1.0),   # 菜粕
    "SA888.LOCAL":  (0.5/10000,0.5/10000, 20,   1.0),   # 纯碱
    "SF888.LOCAL":  (1/10000,  1/10000,   5,   2.0),   # 硅铁
    "SM888.LOCAL":  (1/10000,  1/10000,   5,   2.0),   # 锰硅
    "SR888.LOCAL":  (2.5/10000,2.5/10000, 10,   1.0),   # 白糖
    "TA888.LOCAL":  (0.5/10000,0.5/10000,  5,   2.0),   # PTA
    "UR888.LOCAL":  (1/10000,  1/10000,  20,   1.0),   # 尿素
    "ZC888.LOCAL":  (4/10000,  4/10000, 100,   0.2),   # 动力煤
}


# ─────────────────────────────────────────────────────────────────────────────
# 期货多空 Alpha 策略（继承 AlphaStrategy）
# 信号排名靠前 → 做多，排名靠后 → 做空
# ─────────────────────────────────────────────────────────────────────────────

from collections import defaultdict
from vnpy.trader.object import BarData, TradeData
from vnpy.trader.constant import Direction
from vnpy.trader.utility import round_to
from vnpy.alpha import AlphaStrategy


class FuturesLongShortStrategy(AlphaStrategy):
    """
    期货多空 Alpha 策略

    逻辑：
    - 每天根据信号值对所有品种排名
    - 信号最强的 top_k 个品种作为多头候选，最弱的 top_k 个作为空头候选
    - 每次最多换出 n_drop 个品种（降低换手率）
    - 持仓不足 min_hold_days 天的品种不允许换出（避免过度换仓）

    信号对齐说明（无前视偏差）：
      T 日因子 → 预测 T+1 收益 → T 日收盘后挂单 → T+1 开盘撮合成交
    """

    top_k: int = 5            # 多头 / 空头各持几个品种
    n_drop: int = 2           # 每次最多换出几个品种（多头/空头各自限制）
    min_hold_days: int = 1    # 最小持仓天数（未达到则不允许换出）
    price_add: float = 0.002  # 报单价格偏离比例

    def on_init(self) -> None:
        """策略初始化"""
        # 记录每个品种的持仓天数
        self.holding_days: defaultdict = defaultdict(int)
        self.write_log("FuturesLongShortStrategy 初始化完成")

    def on_trade(self, trade: TradeData) -> None:
        """成交回调：平仓时清除持仓天数记录"""
        # 多头平仓（SELL）或空头平仓（COVER）都清零持仓天数
        if trade.direction == Direction.SHORT and self.pos_data.get(trade.vt_symbol, 0) == 0:
            self.holding_days.pop(trade.vt_symbol, None)
        elif trade.direction == Direction.LONG and self.pos_data.get(trade.vt_symbol, 0) == 0:
            self.holding_days.pop(trade.vt_symbol, None)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """K 线推送：根据信号调仓（含换手率控制）"""
        signal_df: pl.DataFrame = self.get_signal()
        if signal_df.is_empty():
            return

        # 只保留当前有行情的品种，并按信号排序
        available_symbols = set(bars.keys())
        signal_df = (
            signal_df
            .filter(pl.col("vt_symbol").is_in(available_symbols))
            .sort("signal", descending=True)
        )

        if signal_df.is_empty():
            return

        n = len(signal_df)
        k = min(self.top_k, n // 2)    # 防止品种数量不足

        # ── 当前持仓品种，并更新持仓天数 ─────────────────────────────────
        pos_symbols: set[str] = {s for s, p in self.pos_data.items() if p != 0}
        for vt_symbol in pos_symbols:
            self.holding_days[vt_symbol] += 1

        # ── 目标多头 / 空头候选池 ─────────────────────────────────────────
        target_long:  list[str] = list(signal_df["vt_symbol"][:k])
        target_short: list[str] = list(signal_df["vt_symbol"][-k:])

        cur_long:  set[str] = {s for s, p in self.pos_data.items() if p > 0}
        cur_short: set[str] = {s for s, p in self.pos_data.items() if p < 0}

        # ── 多头换仓：找出需要退出的品种，限制每次最多换 n_drop 个 ────────
        long_to_exit = cur_long - set(target_long)
        # 持仓天数不足 min_hold_days 的不允许换出
        long_to_exit = {
            s for s in long_to_exit
            if self.holding_days[s] >= self.min_hold_days
        }
        # 每次最多换出 n_drop 个（按持仓天数最长的先换）
        long_to_exit = set(
            sorted(long_to_exit, key=lambda s: -self.holding_days[s])[:self.n_drop]
        )

        # 空头换仓同理
        short_to_exit = cur_short - set(target_short)
        short_to_exit = {
            s for s in short_to_exit
            if self.holding_days[s] >= self.min_hold_days
        }
        short_to_exit = set(
            sorted(short_to_exit, key=lambda s: -self.holding_days[s])[:self.n_drop]
        )

        # ── 计算最终目标持仓 ──────────────────────────────────────────────
        # 保留没有退出的原仓位，再补入新的目标品种
        final_long  = (cur_long  - long_to_exit)
        final_short = (cur_short - short_to_exit)

        # 补入新多头（从目标候选里按信号强度顺序补到 top_k 个）
        for s in target_long:
            if len(final_long) >= k:
                break
            if s not in final_long and s not in final_short:
                final_long.add(s)

        # 补入新空头
        for s in reversed(target_short):  # 信号最弱的优先进空头
            if len(final_short) >= k:
                break
            if s not in final_short and s not in final_long:
                final_short.add(s)

        # ── 平掉需要退出的仓位 ───────────────────────────────────────────
        for vt_symbol in long_to_exit | short_to_exit:
            self.set_target(vt_symbol, 0)

        # ── 设置目标持仓 ─────────────────────────────────────────────────
        for vt_symbol in final_long:
            self.set_target(vt_symbol, 1)

        for vt_symbol in final_short:
            self.set_target(vt_symbol, -1)

        # ── 执行调仓 ──────────────────────────────────────────────────────
        self.execute_trading(bars, price_add=self.price_add)


# ─────────────────────────────────────────────────────────────────────────────
# 数据处理器（必须定义在模块顶层，否则无法 pickle 保存 dataset）
#
# 处理顺序：
#   1. drop_na  : 删除含 NaN 的行（特征+label 全部检查）
#   2. feat_norm: 对所有特征做截面 rank 归一化（±1.73 范围，消除量纲差异）
#                 Alpha158 特征量级差距可达 1000x，不归一化 MLP 无法收敛
#   3. label_norm: 对 label 做截面 zscore 归一化（标准 Qlib 做法）
# ─────────────────────────────────────────────────────────────────────────────


def _get_feature_names(df) -> list[str]:
    """获取特征列名（排除 datetime, vt_symbol, label）"""
    return df.columns[2:-1]


def learn_processor_drop_na(df):
    """删除特征和 label 中含 NaN 的行"""
    return process_drop_na(df, names=None)


def learn_processor_feat_norm(df):
    """对所有特征做截面 rank 归一化（消除量纲差异，MLP 收敛必需）"""
    feat_names = _get_feature_names(df)
    return process_cs_rank_norm(df, names=feat_names)


def learn_processor_label_norm(df):
    """对 label 做截面 zscore 归一化"""
    return process_cs_norm(df, names=["label"], method="zscore")


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:

    # ── Step 1  初始化 AlphaLab ───────────────────────────────────────────
    print("=" * 60)
    print("Step 1  初始化 AlphaLab")
    print("=" * 60)
    lab = AlphaLab(LAB_PATH)

    # 注册合约参数（回测用）
    for vt_symbol, (lr, sr, sz, pt) in CONTRACT_SETTINGS.items():
        lab.add_contract_setting(
            vt_symbol,
            long_rate=lr,
            short_rate=sr,
            size=sz,
            pricetick=pt,
        )
    print(f"已注册 {len(CONTRACT_SETTINGS)} 个合约参数")

    # ── Step 2  加载数据 ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 2  加载数据")
    print("=" * 60)
    df: pl.DataFrame | None = lab.load_bar_df(
        vt_symbols=VT_SYMBOLS,
        interval=Interval.DAILY,
        start=TRAIN_PERIOD[0],
        end=TEST_PERIOD[1],
        extended_days=EXTENDED_DAYS,
    )

    if df is None or df.is_empty():
        print("❌  未加载到数据，请先运行 prepare_futures_data.py")
        return

    print(f"数据形状：{df.shape}  ({df['datetime'].min()} ~ {df['datetime'].max()})")
    print(f"品种列表：{sorted(df['vt_symbol'].unique().to_list())}")

    # ── Step 3  构建 Alpha158 因子集 ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 3  构建 Alpha158 因子集（158 个价量因子）")
    print("=" * 60)

    dataset = Alpha158(
        df=df,
        train_period=TRAIN_PERIOD,
        valid_period=VALID_PERIOD,
        test_period=TEST_PERIOD,
    )

    # ── 数据处理器注册（顺序严格）────────────────────────────────────────
    # infer_processor:  特征截面 rank 归一化（推断时也生效，训练/推断分布一致）
    #   → process_data 中：infer_df = raw_df → infer_proc → infer_df
    # learn_processor:  在 infer_df 基础上继续做 drop_na + label 归一化
    #   → process_data 中：learn_df = infer_df → learn_proc → learn_df
    dataset.add_processor("infer", learn_processor_feat_norm)   # 特征 rank 归一化
    dataset.add_processor("learn", learn_processor_drop_na)     # 删含 NaN 行
    dataset.add_processor("learn", learn_processor_label_norm)  # label zscore

    print("正在并行计算因子（首次约 2~5 分钟）...")
    dataset.prepare_data(max_workers=4)
    dataset.process_data()

    print(f"因子矩阵（learn）：{dataset.learn_df.shape}")

    # 可选：保存 dataset
    if SAVE_ARTIFACTS:
        lab.save_dataset(ARTIFACT_NAME, dataset)
        print(f"✅ dataset 已保存：{ARTIFACT_NAME}")

    # ── Step 4  训练 MLP 模型 ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 4  训练 MLP 模型")
    print("=" * 60)

    import numpy as np
    from scipy.stats import spearmanr

    model = MlpModel(**MLP_PARAMS)

    print("[MLP] 训练中...")
    try:
        model.fit(dataset)
    except Exception as e:
        print(f"  ❌ 训练失败：{e}")
        return

    # ── Step 5  生成信号 ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 5  生成测试区间信号")
    print("=" * 60)

    test_infer_base: pl.DataFrame = dataset.fetch_infer(Segment.TEST).sort(["datetime", "vt_symbol"])

    try:
        pred_arr: np.ndarray = model.predict(dataset, Segment.TEST)
    except Exception as e:
        print(f"  ❌ 预测失败：{e}")
        return

    sig_df: pl.DataFrame = test_infer_base.select(["datetime", "vt_symbol"]).with_columns(
        pl.Series("signal", pred_arr)
    )

    # ── Step 6  IC 分析 ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 6  IC 统计")
    print("=" * 60)

    swl = (
        sig_df
        .join(test_infer_base.select(["datetime", "vt_symbol", "label"]),
              on=["datetime", "vt_symbol"], how="inner")
        .drop_nulls(subset=["signal", "label"])
    )
    ic_vals: list[float] = []
    for _, grp in swl.group_by("datetime"):
        if len(grp) < 3:
            continue
        c, _ = spearmanr(grp["signal"].to_numpy(), grp["label"].to_numpy())
        ic_vals.append(float(c))

    if ic_vals:
        s = pl.Series(ic_vals).fill_nan(None).drop_nulls()
        ic_mean = float(s.mean())
        ic_std  = float(s.std())
        icir    = ic_mean / ic_std if ic_std > 0 else 0.0
        ic_pos  = float((s > 0).mean())
    else:
        ic_mean = ic_std = icir = ic_pos = float("nan")

    print(f"  IC Mean  : {ic_mean:+.4f}  （|0.03| 以上认为有效）")
    print(f"  IC Std   : {ic_std:.4f}")
    print(f"  ICIR     : {icir:+.4f}  （|0.5| 以上认为稳定）")
    print(f"  IC>0 占比 : {ic_pos:.1%}")

    # ── AUC 计算 ────────────────────────────────────────────────────────────
    # 定义：signal > 0 预测上涨，label > 0 实际上涨，计算二分类 AUC
    # AUC=0.5 表示随机猜测，AUC>0.5 表示有预测能力
    from sklearn.metrics import roc_auc_score
    try:
        auc_data = swl.drop_nulls(subset=["signal", "label"])
        y_score = auc_data["signal"].to_numpy()
        y_true  = (auc_data["label"].to_numpy() > 0).astype(int)  # 实际涨 = 1
        # 至少要有正负两类样本才能计算 AUC
        if y_true.sum() > 0 and (1 - y_true).sum() > 0:
            auc = roc_auc_score(y_true, y_score)
            print(f"  AUC      : {auc:.4f}  （0.5=随机，>0.52 认为有效）")
        else:
            print(f"  AUC      : N/A（样本全为同一类）")
    except Exception as e:
        print(f"  AUC      : 计算失败 ({e})")

    # ── Step 7  回测 ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 7  回测")
    print("=" * 60)

    engine = BacktestingEngine(lab)
    engine.set_parameters(
        vt_symbols=VT_SYMBOLS,
        interval=Interval.DAILY,
        start=datetime.strptime(TEST_PERIOD[0], "%Y-%m-%d"),
        end=datetime.strptime(TEST_PERIOD[1],   "%Y-%m-%d"),
        capital=5_000_000,
        risk_free=0.015,
        annual_days=243,
    )
    engine.add_strategy(
        FuturesLongShortStrategy,
        # top_k=5 多空各5个，n_drop=1 每次最多换1个（降低换手），min_hold_days=3 最少持仓3天
        # 手续费是最大杀手：之前每天换7笔，手续费吃掉64%利润 → 减少换手是首要优化
        setting={"top_k": 5, "n_drop": 1, "min_hold_days": 3, "price_add": 0.002},
        signal_df=sig_df,
    )
    engine.load_data()
    engine.run_backtesting()

    daily_df = engine.calculate_result()
    if daily_df is not None:
        stats = engine.calculate_statistics()
        ann_ret     = stats["annual_return"]
        sharpe      = stats["sharpe_ratio"]
        max_ddpct   = stats["max_ddpercent"]
        rdr         = stats["return_drawdown_ratio"]
        n_trades    = stats["total_trade_count"]
        commission  = stats["total_commission"]

        print(f"  年化收益率    : {ann_ret:>8.2f} %")
        print(f"  Sharpe Ratio  : {sharpe:>8.3f}")
        print(f"  最大回撤百分比: {max_ddpct:>8.2f} %")
        print(f"  收益回撤比    : {rdr:>8.3f}")
        print(f"  总交易笔数    : {n_trades:>8}")
        print(f"  总手续费      : {commission:>12,.0f}")

        try:
            engine.show_chart()
        except Exception:
            pass
    else:
        print("  ❌ 回测无成交")
        return

    # ── Step 8  保存模型和信号 ───────────────────────────────────────────
    if SAVE_ARTIFACTS:
        lab.save_model(ARTIFACT_NAME, model)
        lab.save_signal(ARTIFACT_NAME, sig_df)
        print(f"\n✅ 模型和信号已保存：{ARTIFACT_NAME}")


if __name__ == "__main__":
    main()
