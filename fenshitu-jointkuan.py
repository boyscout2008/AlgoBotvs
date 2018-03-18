# 导入函数库
import jqdata
import pandas as pd
import numpy as np

## 初始化函数，设定基准等等
def initialize(context):
    set_params(context)
    # 只获取铁矿石主力合约；要支持其他品种，参考品种数组
    g.future = get_dominant_future('I')
    
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
 
    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
      # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security=get_dominant_future('I'))
      # 开盘时运行
    run_daily( market_open, time='open', reference_security=get_dominant_future('I'))
    run_daily(market_open_daytime, time='9:00')
      # 盘中按分钟数据运行
    run_daily( handle_bar_min, time='every_bar', reference_security=get_dominant_future('I'))
      # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security=get_dominant_future('I'))

def set_params(context):
    # 交易所状态：-1-关闭， 0-开盘前初始化， 1-开盘， 2-交易时间
    g.status = -1
    # 交易日开盘时间 夜盘模式情况下与交易日并非同一天
    g.open_time = None
    # 最大unit数目
    g.limit_unit = 6
    # 每次交易unit数目
    g.unit = 0
    # 持仓状态
    g.position = 0
    # 最高价指标，用作移动止损
    g.price_mark = 0
    # 最近一次交易的合约
    g.last_future = None
    # 上一次交易的价格
    g.last_price = 0
'''
def daily_reset(context):
    # 当日开盘价
    g.open_price= 0.0
    # 当日开盘时间（夜盘模式实际日期并非当日）
    g.open_time = context.current_dt
    # 交易日日期
    g.trading_date = datetime.datetime.now().date() #TODO: 夜盘推迟到下个交易日
    # 分时均价矩阵
    g.avg_price = pd.DataFrame()
'''
# 最后15分钟为尾盘时间；
# 考虑到夜盘模式，不能比较日期： start和end都是h:m:s格式
def check_time(start_time, end_time, cur_time):
    cur_time = cur_time.time()
    
    start_H_M = start_time.split(':')
    start_time = datetime.time(int(start_H_M[0]), int(start_H_M[1]))
    end_H_M = end_time.split(':')
    end_time = datetime.time(int(end_H_M[0]), int(end_H_M[1]))
    
    if cur_time >= start_time and cur_time <= end_time:
        return True
    else:
        return False
    
## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    if g.status != -1:
        log.info("ERROR:", g.status, str(context.current_dt.time()))
    #assert(g.status == -1)
    
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    if 1: # TODO - check the trading day
        send_message('有效交易日，美好的一天~')
    else:
        invalid_trading = True
        
    g.status = 0
    
## 开盘时运行函数
def market_open(context):
    if g.status != 0:
        return
    
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))

    g.open_time = context.current_dt
    g.status = 1
    
def market_open_daytime(context):
    if g.status == 2:
        return
    
    if g.status == -1:
        log.info("该交易日没有获取夜盘数据，忽略！")
        return
    
    log.info('函数运行时间(market_open_daytime):'+str(context.current_dt.time()))

    g.open_time = context.current_dt
    g.status = 1
    
# 根据分钟级k线捕捉交易机会
def handle_bar_min(context):
    # 忽略不完整日交易数据，比如回测的起始日期没有夜盘数据
    if g.status == 1:
        g.status = 2
        
    if g.status != 2:
        #log.info("忽略回测中数据不完整的交易日, 或没有夜盘的交易时间！")
        return
    
    future = g.future
    # 获取单个品种的数据结构为：pandas.DataFrame
    bars = get_price(future, start_date=g.open_time, 
		                          end_date=context.current_dt, frequency='minute', fields=['close', 'volume', 'money'])

    total_volume = bars.iloc[:, 1].sum()
    total_money = bars.iloc[:, 2].sum()
    
    # 连续三个k线没有交易量则调整开盘时间到日盘模式
    if len(bars) == 3 and total_volume == 0:
        log.info(bars)
        log.info("下一交易日没有夜盘！")
        g.status = 0
        return
    
    if total_volume > 0 and total_money > 0:# and total_volume < 150000:
        #current_avg = round(total_money/total_volume/100, 1) # 100吨/手
        cur_avg = total_money/total_volume/100 # 100吨/手
        if (cur_avg - int(cur_avg) >= 0.5):
            cur_avg = int(cur_avg) + 0.5
        else:
            cur_avg = int(cur_avg)
            
        cur_price = bars.iloc[-1, 0]
        
        
        #log.info(cur_avg, cur_price)
        
        # 交易时间设定（比如尾盘只平不开，不考虑日期，只看时间区间）
        cur_time = bars.index[-1]
        
        IsLast = check_time("14:55", "15:00", cur_time)

        if IsLast:
            log.info(cur_avg, cur_price)
        
        return
        
        diff = cur_price - cur_avg
        if diff >= 3:
            if len(context.portfolio.long_positions) > 0:
                order_target(security, 0, cur_price, 'short') # 平多单
            if len(context.portfolio.short_positions) == 0:
                order(future, 1, cur_price, 'short') # 开空单
        if diff <= 3:
            if len(context.portfolio.short_positions) > 0:
                order_target(security, 0, cur_price, 'long') # 平空单
            if len(context.portfolio.long_positions) == 0:
                order(future, 1, cur_price, 'long') # 开多单
        # TODO：在模拟交易中开通微信通知功能
        send_message("xxxx", channel='weixin')
        
        log.info(cur_avg, cur_price)

## 收盘后运行函数  
def after_market_close(context):
    if g.status != 2:
        return
    
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
        
    g.status = -1
    log.info('一天结束')
    log.info('##############################################################')
