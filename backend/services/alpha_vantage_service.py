# -*- coding: utf-8 -*-
"""Alpha Vantage API：拉取股票日线等数据，供同步到 MySQL 或直接返回。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from config import Config


class AlphaVantageService:
    """调用 Alpha Vantage 获取行情，返回与 stock_data 表结构一致的字典列表。"""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or Config.ALPHA_VANTAGE_API_KEY

    def fetch_daily(self, symbol: str, output_size: str = "compact") -> List[Dict[str, Any]]:
        """
        获取单只股票日线（TIME_SERIES_DAILY）。
        返回: [ { "symbol", "date", "close", "price_change", "volume" }, ... ]
        price_change 为当日 (close - open) / open * 100。
        """
        if not self._api_key:
            return []
        try:
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": self._api_key,
                "outputsize": output_size,
            }
            r = requests.get(self.BASE_URL, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []

        series = data.get("Time Series (Daily)")
        if not series:
            return []

        rows = []
        for date_str, ohlcv in series.items():
            try:
                open_ = float(ohlcv.get("1. open", 0) or 0)
                close = float(ohlcv.get("4. close", 0) or 0)
                vol = ohlcv.get("5. volume")
                volume = int(vol) if vol is not None else None
                if open_ and open_ != 0:
                    price_change = round((close - open_) / open_ * 100, 4)
                else:
                    price_change = 0.0
                rows.append({
                    "symbol": symbol,
                    "date": date_str,
                    "close": close,
                    "price_change": price_change,
                    "volume": volume,
                })
            except (TypeError, ValueError):
                continue
        return rows

    def fetch_symbols(self, symbols: List[str], output_size: str = "compact") -> List[Dict[str, Any]]:
        """多只股票日线合并为一张表（与 stock_data 列一致）。"""
        all_rows = []
        for sym in symbols:
            rows = self.fetch_daily(sym, output_size=output_size)
            all_rows.extend(rows)
        return all_rows
