import math
import random
import time

class SimMarket:
    def __init__(self, symbol: str = "SPY", start_price: float = 480.0):
        self.symbol = symbol
        self.price = start_price
        self.t0 = time.time()

    def tick(self) -> dict:
        wave = 0.25 * math.sin((time.time() - self.t0) / 15.0)
        shock = random.gauss(0, 0.15)
        self.price = max(1.0, self.price + wave + shock)
        return {"symbol": self.symbol, "price": round(self.price, 2), "ts": time.time()}
