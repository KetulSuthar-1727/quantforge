"""Run the opt-in read-only scheduled scanner from a terminal."""
import os
import signal
import threading

from dotenv import load_dotenv

from engine.dataset import fetch_alpaca_dataset
from engine.market_data import AlpacaMarketDataProvider
from engine.scanner import StockScanner
from engine.scheduler import ScanScheduler, SchedulerConfig, SchedulerStore
from engine.strategy import get_strategy


def build_scheduler():
    load_dotenv(".env")
    symbols = [part.strip() for part in os.getenv("QF_SCAN_SYMBOLS", "AAPL,MSFT,NVDA").split(",") if part.strip()]
    strategy_id = os.getenv("QF_SCAN_STRATEGY", "moving_average")
    interval = os.getenv("QF_SCAN_INTERVAL_SECONDS", "300")
    timeframe = os.getenv("QF_SCAN_TIMEFRAME", "1Day")
    try:
        parameters = {"fast_window": int(os.getenv("QF_SCAN_FAST_WINDOW", "3")),
                     "slow_window": int(os.getenv("QF_SCAN_SLOW_WINDOW", "5"))} if strategy_id == "moving_average" else {
                     "window": int(os.getenv("QF_SCAN_WINDOW", "20")),
                     "entry_zscore": float(os.getenv("QF_SCAN_ENTRY_ZSCORE", "2.0"))}
        config = SchedulerConfig(interval_seconds=int(interval))
    except ValueError as exc:
        raise ValueError("Invalid scheduler numeric configuration.") from exc
    provider = AlpacaMarketDataProvider()
    scanner = StockScanner(symbols, get_strategy(strategy_id, **parameters),
                           lambda symbol: fetch_alpaca_dataset(provider, symbol=symbol, interval=timeframe),
                           timeframe=timeframe)
    store = SchedulerStore(os.getenv("QF_SCHEDULER_DB", "var/scheduler.sqlite3"))
    return ScanScheduler(scanner, config=config, store=store)


def main():
    scheduler = build_scheduler()
    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    scheduler.start()
    print("QuantForge scheduled scanner running (read-only; automatic orders disabled). Ctrl-C to stop.")
    try:
        stopped.wait()
    finally:
        scheduler.stop(timeout=30)
        print(scheduler.status())


if __name__ == "__main__":
    main()
