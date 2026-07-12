from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import yfinance as yf
from datetime import datetime
import math

app = FastAPI()

# CORS 설정 (HTML 파일에서 호출 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/etf/{ticker}")
def get_etf_info(ticker: str):
    """ETF 기본 정보 반환"""
    try:
        etf = yf.Ticker(ticker.upper())
        info = etf.info

        if not info or "regularMarketPrice" not in info and "currentPrice" not in info and "navPrice" not in info:
            raise HTTPException(status_code=404, detail=f"티커 '{ticker}'를 찾을 수 없습니다.")

        # 현재가 (여러 필드 중 존재하는 것)
        price = (
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("navPrice")
            or 0
        )

        # 설정일 (Unix timestamp → 날짜 문자열)
        inception_ts = info.get("fundInceptionDate")
        inception_date = (
            datetime.fromtimestamp(inception_ts).strftime("%Y-%m-%d")
            if inception_ts
            else None
        )

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName"),
            "price": price,
            "currency": info.get("currency", "USD"),
            "dividend_yield": round((info.get("dividendYield") or 0) * 100, 2),  # % 변환
            "dividend_rate": info.get("dividendRate") or 0,   # 연간 배당금 (달러)
            "expense_ratio": round((info.get("annualReportExpenseRatio") or info.get("totalExpenseRatio") or 0) * 100, 2),
            "inception_date": inception_date,
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "total_assets": info.get("totalAssets"),
            "category": info.get("category"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etf/{ticker}/history")
def get_etf_history(ticker: str, period: str = "max"):
    """ETF 가격 이력 반환 (그래프용)
    period: 1y, 3y, 5y, 10y, max
    """
    try:
        # period를 yfinance 형식으로 변환
        period_map = {
            "1y": "1y",
            "3y": "3y",
            "5y": "5y",
            "10y": "10y",
            "max": "max",
        }
        yf_period = period_map.get(period, "max")

        etf = yf.Ticker(ticker.upper())
        hist = etf.history(period=yf_period)

        if hist.empty:
            raise HTTPException(status_code=404, detail="가격 데이터가 없습니다.")

        # 날짜, 종가만 추출해서 반환
        data = [
            {
                "date": str(index.date()),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if not math.isnan(row["Volume"]) else 0,
            }
            for index, row in hist.iterrows()
        ]

        return {
            "ticker": ticker.upper(),
            "period": period,
            "count": len(data),
            "data": data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etf/{ticker}/dividends")
def get_etf_dividends(ticker: str):
    """ETF 배당 이력 반환"""
    try:
        etf = yf.Ticker(ticker.upper())
        divs = etf.dividends

        if divs.empty:
            return {"ticker": ticker.upper(), "dividends": []}

        data = [
            {
                "date": str(index.date()),
                "amount": round(float(amount), 4),
            }
            for index, amount in divs.items()
        ]

        # 연간 배당금 합계 계산
        div_df = divs.copy()
        div_df.index = div_df.index.tz_localize(None) if div_df.index.tz else div_df.index
        annual = {}
        for date, amount in divs.items():
            year = date.year
            annual[year] = round(annual.get(year, 0) + float(amount), 4)

        return {
            "ticker": ticker.upper(),
            "total_count": len(data),
            "dividends": data,
            "annual_summary": [
                {"year": y, "total": a} for y, a in sorted(annual.items())
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}

app.mount("/", StaticFiles(directory="static", html=True), name="static")