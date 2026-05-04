"""
主连数据生成器（交易所通用）

从 vnpy 数据库中已有的原始合约日K线，批量重建所有历史主连（888）合约数据。

核心功能：
  - 根据每日持仓量自动识别主力 / 次主力合约
  - 按成交量加权合成 888 K 线并写回数据库
  - 同时维护 MappingStore 主力映射表

快速使用：
    # 命令行（重建 DCE 全部品种）
    uv run python ai/agent/main_contract_builder/run.py --exchange DCE

    # Python 调用
    from ai.agent.main_contract_builder.builder import rebuild_all
    rebuild_all(exchange="DCE", varieties=["a", "m", "y"])
"""
from .builder import rebuild_variety, rebuild_all

__all__ = ["rebuild_variety", "rebuild_all"]
