"""
大商所 API 测试脚本

功能：
    1. 从 .env 读取 DCE_API_KEY 和 DCE_API_SECRET
    2. 登录获取 Bearer token
    3. 测试核心接口（交易日、品种、行情、仓单、会员排名）

运行方式：
    uv run python ai/data_process/test_dce_api.py

API 文档：ai/doc/dceapiv1.0.md
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import requests
from dotenv import load_dotenv

# 加载 .env 配置
load_dotenv(ROOT / ".env")

# ═══════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════

API_KEY = os.getenv("DCE_API_KEY")
API_SECRET = os.getenv("DCE_API_SECRET")
BASE_URL = "http://www.dce.com.cn/dceapi"

if not API_KEY or not API_SECRET:
    print("❌ 错误：未在 .env 中找到 DCE_API_KEY 或 DCE_API_SECRET")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════════

def print_section(title: str) -> None:
    """打印分隔线标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_response(resp: dict, max_items: int = 3) -> None:
    """打印 API 响应（截断长列表）"""
    if resp.get("success"):
        print(f"✅ 请求成功 (code: {resp['code']})")
        data = resp.get("data")
        
        if isinstance(data, dict):
            print(f"   返回字段数: {len(data)}")
            for k, v in list(data.items())[:5]:  # 只显示前 5 个字段
                if isinstance(v, list):
                    print(f"   {k}: [{len(v)} items]")
                else:
                    print(f"   {k}: {v}")
        elif isinstance(data, list):
            print(f"   返回记录数: {len(data)}")
            if data:
                print(f"   示例数据（前 {min(max_items, len(data))} 条）:")
                for i, item in enumerate(data[:max_items], 1):
                    if isinstance(item, dict):
                        # 显示每条记录的关键字段
                        key_fields = {k: v for k, v in list(item.items())[:6]}
                        print(f"     [{i}] {key_fields}")
                    else:
                        print(f"     [{i}] {item}")
        else:
            print(f"   data: {data}")
    else:
        print(f"❌ 请求失败 (code: {resp.get('code')})")
        print(f"   msg: {resp.get('msg')}")
        print(f"   requestId: {resp.get('requestId')}")


def api_request(
    method: str,
    endpoint: str,
    headers: dict | None = None,
    json_data: dict | None = None,
    timeout: int = 10
) -> dict:
    """通用 API 请求函数"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=timeout)
        else:
            raise ValueError(f"不支持的方法: {method}")
        
        resp.raise_for_status()
        return resp.json()
    
    except requests.exceptions.Timeout:
        return {"success": False, "code": -1, "msg": f"请求超时 ({timeout}s)"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "code": -1, "msg": f"请求失败: {e}"}
    except Exception as e:
        return {"success": False, "code": -1, "msg": f"未知错误: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
# API 测试函数
# ═══════════════════════════════════════════════════════════════════════════

def test_login() -> str | None:
    """
    测试登录接口，返回 Bearer token
    接口: POST /cms/auth/accessToken
    """
    print_section("1. 测试登录")
    
    headers = {"apikey": API_KEY}
    json_data = {"secret": API_SECRET}
    
    resp = api_request("POST", "/cms/auth/accessToken", headers=headers, json_data=json_data)
    print_response(resp)
    
    if resp.get("success"):
        token = resp["data"]["token"]
        expires_in = resp["data"]["expiresIn"]
        print(f"   Token 有效期: {expires_in}s ({expires_in / 60:.1f} 分钟)")
        return token
    else:
        print("❌ 登录失败，无法继续测试")
        return None


def test_current_trade_date(token: str) -> str | None:
    """
    测试当前交易日接口
    接口: GET /forward/publicweb/maxTradeDate
    """
    print_section("2. 测试当前交易日")
    
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    resp = api_request("GET", "/forward/publicweb/maxTradeDate", headers=headers)
    print_response(resp)
    
    if resp.get("success"):
        trade_date = resp["data"]["tradeDate"]
        print(f"   当前交易日: {trade_date}")
        return trade_date
    return None


def test_variety_list(token: str) -> None:
    """
    测试品种列表接口
    接口: GET /forward/publicweb/variety
    """
    print_section("3. 测试品种列表")
    
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    resp = api_request("GET", "/forward/publicweb/variety", headers=headers)
    print_response(resp, max_items=5)


def test_day_quotes(token: str, trade_date: str) -> None:
    """
    测试日行情接口（期货-全部品种）
    接口: POST /forward/publicweb/dailystat/dayQuotes
    """
    print_section("4. 测试日行情（期货-全部品种）")
    
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    json_data = {
        "varietyId": "all",  # 查询全部品种
        "tradeDate": trade_date,
        "tradeType": "1",    # 1=期货
        "lang": "zh"
    }
    
    resp = api_request("POST", "/forward/publicweb/dailystat/dayQuotes", headers=headers, json_data=json_data)
    print_response(resp, max_items=5)  # 显示前5个品种


def test_warehouse_bill(token: str, trade_date: str) -> None:
    """
    测试仓单日报接口（豆一）
    接口: POST /forward/publicweb/dailystat/wbillWeeklyQuotes
    """
    print_section("5. 测试仓单日报（豆一）")
    
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    json_data = {
        "varietyId": "a",  # 豆一
        "tradeDate": trade_date
    }
    
    resp = api_request("POST", "/forward/publicweb/dailystat/wbillWeeklyQuotes", headers=headers, json_data=json_data)
    print_response(resp, max_items=3)


def test_member_deal_posi(token: str, trade_date: str) -> None:
    """
    测试会员成交持仓排名接口（豆一主力合约）
    接口: POST /forward/publicweb/dailystat/memberDealPosi
    """
    print_section("6. 测试会员成交持仓排名（豆一-a2511）")
    
    headers = {
        "apikey": API_KEY,
        "Authorization": f"Bearer {token}"
    }
    
    json_data = {
        "varietyId": "a",
        "tradeDate": trade_date,
        "contractId": "a2511",  # 豆一 2025年11月合约
        "tradeType": "1"
    }
    
    resp = api_request("POST", "/forward/publicweb/dailystat/memberDealPosi", headers=headers, json_data=json_data)
    
    # 会员排名数据结构较复杂，单独处理
    if resp.get("success"):
        print(f"✅ 请求成功 (code: {resp['code']})")
        data = resp.get("data", {})
        
        print(f"   成交量汇总: {data.get('todayQty', 0)}")
        print(f"   持买单量汇总: {data.get('todayBuyQty', 0)}")
        print(f"   持卖单量汇总: {data.get('todaySellQty', 0)}")
        
        # 显示成交量前3名
        qty_list = data.get("qtyFutureList", [])
        if qty_list:
            print(f"   成交量排名（前3）:")
            for item in qty_list[:3]:
                print(f"     [{item['rank']}] {item['qtyAbbr']}: {item['todayQty']} (增减: {item['qtySub']})")
    else:
        print_response(resp)


# ═══════════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """主测试流程"""
    print("\n" + "━" * 70)
    print("  大商所 API 测试脚本")
    print("  测试时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("━" * 70)
    
    # Step 1: 登录
    token = test_login()
    if not token:
        sys.exit(1)
    
    # Step 2: 当前交易日
    current_trade_date = test_current_trade_date(token)
    
    # 使用历史交易日（确保有数据）
    trade_date = "20251014"  # 使用文档示例中的历史日期
    if current_trade_date and current_trade_date != trade_date:
        print(f"   💡 使用历史交易日 {trade_date} 进行测试（当前交易日: {current_trade_date}）")
    
    # Step 3: 品种列表
    test_variety_list(token)
    
    # Step 4: 日行情
    test_day_quotes(token, trade_date)
    
    # Step 5: 仓单日报
    test_warehouse_bill(token, trade_date)
    
    # Step 6: 会员成交持仓排名
    test_member_deal_posi(token, trade_date)
    
    print_section("测试完成")
    print("✅ 所有接口测试完毕")
    print("\n💡 提示：如需测试更多接口，请参考 ai/doc/dceapiv1.0.md")


if __name__ == "__main__":
    main()
