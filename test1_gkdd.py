'''backtest
start: 2017-12-20 20:50:00
end: 2017-12-21 20:50:00
period: 1m
exchanges: [{"eid":"Futures_CTP","currency":"FUTURES"}]
'''

class Trader:
    def __init__(self, q, symbol):
        self.q = q
        self.symbol = symbol
        self.position = 0
        self.vwma = 0.0
        self.totalVolume = 0
        self.isPending = False

    def onOpen(self, task, ret):
        if ret:
            self.position = ret['position']['Amount'] * (1 if (ret['position']['Type'] == PD_LONG or ret['position']['Type'] == PD_LONG_YD) else -1)
        Log(task["desc"], "Position:", self.position, ret)
        self.isPending = False

    def onCover(self, task, ret):
        self.isPending = False
        self.position = 0
        Log(task["desc"], ret)

    def onTick(self):
        if self.isPending:
            return
        
        ct = exchange.SetContractType(self.symbol)
        if not ct:
            return

        r = exchange.GetRecords()
        if not r:
            return
        
        pVolume = self.totalVolume
        pVwma = self.vwma
        #Log(task["desc"], pVolume)
        #Log(task["desc"], pVwma)
        
        self.totalVolume = r[-1].Volume + pVolume
        self.vwma = (r[-1].Close*r[-1].Volume + pVwma * pVolume)/self.totalVolume
        
        #TODO: 为铁矿石合约四舍五入
        diff = r[-1].Close - self.vwma
        #diff = r[-1].Close - 539 #self.vwma
 
        # TODO: 先测试固定offset=3和止盈点位1，之后完成外部参数设置，再完成内部参数自适应
        if abs(diff) > 3 and self.position == 0:
            self.isPending = True
            #高空低多开仓
            self.q.pushTask(exchange, self.symbol, ("sell" if diff > 0 else "buy"), 1, self.onOpen)
            #追空追多
            #self.q.pushTask(exchange, self.symbol, ("buy" if diff > 0 else "sell"), 1, self.onOpen)
        # 高空低多平仓策略
        if abs(diff) >= 1 and ((diff < 0 and self.position < 0) or (diff > 0 and self.position > 0)):
            self.isPending = True
            self.q.pushTask(exchange, self.symbol, ("closebuy" if self.position > 0 else "closesell"), 1, self.onCover)
        
        
    def _onTick(self):
        if self.isPending:
            return
        ct = exchange.SetContractType(self.symbol)
        if not ct:
            return

        r = exchange.GetRecords()
        if not r or len(r) < 35:
            return
        macd = TA.MACD(r)
        
        diff = macd[0][-2] - macd[1][-2]
        if abs(diff) > 0 and self.position == 0:
            self.isPending = True
            self.q.pushTask(exchange, self.symbol, ("buy" if diff > 0 else "sell"), 1, self.onOpen)
        if abs(diff) > 0 and ((diff > 0 and self.position < 0) or (diff < 0 and self.position > 0)):
            self.isPending = True
            self.q.pushTask(exchange, self.symbol, ("closebuy" if self.position > 0 else "closesell"), 1, self.onCover)

def main():
    q = ext.NewTaskQueue()
    Log(_C(exchange.GetAccount))
    tasks = []
    for symbol in ContractList.split(','):
        tasks.append(Trader(q, symbol.strip()))
    while True:
        if exchange.IO("status"):
            for t in tasks:
                t.onTick()
            q.poll()
            Sleep(1000)
