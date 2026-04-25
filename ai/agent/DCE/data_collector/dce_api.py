"""
DCE API 客户端
提供大商所数据接口的统一封装
"""
import os
import time
import requests
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# 加载环境变量（从项目根目录）
# 当前文件: ai/agent/DCE/data_collector/dce_api.py
# 需要向上5层到达项目根目录: vnpy/
project_root = Path(__file__).parent.parent.parent.parent.parent
env_path = project_root / ".env"

# 打印调试信息（可选）
if not env_path.exists():
    print(f"⚠️ 警告: .env 文件不存在: {env_path}")
    print(f"  当前文件: {__file__}")
    print(f"  项目根目录: {project_root}")

load_dotenv(env_path)


class DCEAPIClient:
    """大商所 API 客户端"""
    
    # 使用正确的 DCE API 地址
    BASE_URL = "http://www.dce.com.cn/dceapi"
    
    def __init__(self):
        self.api_key = os.getenv("DCE_API_KEY")
        self.api_secret = os.getenv("DCE_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("未找到 DCE API 凭证，请检查 .env 文件")
        
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    def _get_token(self) -> str:
        """获取访问令牌（带缓存）"""
        now = datetime.now()
        
        # 检查缓存的 token 是否有效
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token
        
        # 请求新 token
        url = f"{self.BASE_URL}/cms/auth/accessToken"
        headers = {"apikey": self.api_key}
        data = {"secret": self.api_secret}
        
        response = requests.post(url, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success") or result.get("code") != 200:
            raise Exception(f"获取 token 失败: {result.get('msg')}")
        
        token_data = result["data"]
        self._token = token_data["token"]
        # Token 有效期（秒）
        expires_in = token_data.get("expiresIn", 3600)
        self._token_expires_at = now + timedelta(seconds=expires_in - 300)  # 提前5分钟刷新
        
        return self._token
 
    def _api_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """统一的 API 请求方法"""
        token = self._get_token()
        headers = {
            "apikey": self.api_key,  # 同时需要 apikey
            "Authorization": f"Bearer {token}"
        }
        url = f"{self.BASE_URL}{endpoint}"
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success") or result.get("code") != 200:
            raise Exception(f"API请求失败: {result.get('msg')}")
        
        return result.get("data", {})
    
    def get_max_trade_date(self) -> str:
        """获取最新交易日"""
        data = self._api_request("GET", "/forward/publicweb/maxTradeDate")
        return data.get("tradeDate", "")
    
    def get_varieties(self) -> List[Dict]:
        """获取所有品种列表"""
        data = self._api_request("GET", "/forward/publicweb/variety")
        # 响应 data 直接是 list
        if isinstance(data, list):
            return data
        return data.get("list", [])
    
    def get_day_quotes(
        self, 
        trade_date: str, 
        variety_id: str = "all",
        trade_type: str = "1"
    ) -> List[Dict]:
        """
        获取日K线行情
        
        Args:
            trade_date: 交易日（YYYYMMDD）
            variety_id: 品种ID（"all"表示全部）
            trade_type: 交易类型（"1"期货, "2"期权）
        
        Returns:
            行情数据列表
        """
        payload = {
            "varietyId": variety_id,
            "tradeDate": trade_date,
            "tradeType": trade_type,
            "lang": "zh"
        }
        
        data = self._api_request("POST", "/forward/publicweb/dailystat/dayQuotes", data=payload)
        # 响应 data 可能是 list 或 dict
        if isinstance(data, list):
            quotes = data
        else:
            quotes = data.get("list", []) if isinstance(data, dict) else []
        
        # 过滤掉"总计"行
        return [q for q in quotes if q.get("variety") != "总计"]
    
    def get_warehouse_bill(
        self,
        trade_date: str,
        variety_id: str
    ) -> List[Dict]:
        """
        获取仓单日报
        
        Args:
            trade_date: 交易日（YYYYMMDD）
            variety_id: 品种ID
        """
        payload = {
            "varietyId": variety_id,
            "tradeDate": trade_date,
            "lang": "zh"
        }
        
        data = self._api_request("POST", "/forward/publicweb/dailystat/wbillWeeklyQuotes", data=payload)
        return data.get("list", [])
    
    def get_member_ranking(
        self,
        trade_date: str,
        contract_id: str
    ) -> Dict:
        """
        获取会员持仓排名
        
        Args:
            trade_date: 交易日（YYYYMMDD）
            contract_id: 合约代码（如"a2507"）
        """
        payload = {
            "contractId": contract_id,
            "tradeDate": trade_date,
            "lang": "zh"
        }
        
        data = self._api_request("POST", "/forward/publicweb/dailystat/memberDealPosi", data=payload)
        return data
    
    def get_trade_params(self, variety_id: str) -> List[Dict]:
        """
        获取交易参数（保证金、手续费等）
        
        Args:
            variety_id: 品种ID
        """
        payload = {
            "varietyId": variety_id,
            "lang": "zh"
        }
        
        data = self._api_request("POST", "/forward/publicweb/dailystat/dayTradPara", data=payload)
        return data.get("list", [])


# 单例模式
_client_instance: Optional[DCEAPIClient] = None


def get_dce_client() -> DCEAPIClient:
    """获取 DCE API 客户端单例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = DCEAPIClient()
    return _client_instance
