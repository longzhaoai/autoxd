#-*- coding:utf-8 -*-
# Copyright (c) Kang Wang. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# QQ: 1764462457

# Released under the GPL 该软件遵循GPL协议
# account.py - 本地模拟A股卷商资金账户
# Copyright (c) 2016 Wang Kang QQ:1764462457
import numpy as np
import pandas as pd
import sys,time,warnings,unittest,json,datetime,dateutil
from abc import ABCMeta, abstractmethod

"""本地账户 v1.0 2016-5-15"""

class AccountDelegate(object):
    """交易接口, v1.0 包括七个接口"""
    __metaclass__ = ABCMeta
    def Order(self, bSell, code, price, num):
        raise NotImplementedError("Implement Interface")
    def StockList(self):
        raise NotImplementedError("Implement Interface")
    def ZhiJing(self):
        raise NotImplementedError("Implement Interface")
    def ChengJiao(self):
        raise NotImplementedError("Implement Interface")
    def WeiTuoList(self):
        raise NotImplementedError("Implement Interface")
    def CheDanList(self):
        raise NotImplementedError("Implement Interface")
    def CheDan(self, code, weituo_id):
        raise NotImplementedError("Implement Interface")
class BackTestingDelegate(object):
    """回测环境的回调接口"""
    __metaclass__ = ABCMeta
    def getCurTickTime(self):
        """return: str datetime"""
        raise NotImplementedError("Implement Interface")
class BackTesting(BackTestingDelegate):
    def getCurTickTime(self):
        """return: str datetime"""
        return time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))    
def ShouShu(num):
    """"""
    num = int(num /100.0 )*100
    return num
def sxf():
    """手续费, 万3的一般推算"""
    return 0.0016
#状态说明，包含 已成，已撤， 未成
class LocalAcount(AccountDelegate):
    """本地账户， 支持T+1, 无持续化"""
    stocklist_columns = '证券代码|证券名称|证券数量|库存数量|可卖数量|参考成本价|买入均价|参考盈亏成本价|当前价|最新市值|参考浮动盈亏|盈亏比例(%)|在途买入|在途卖出|股东代码'
    zhijing_columns = '余额|可用|参考市值|资产|盈亏'
    chengjiao_columns = "成交日期|成交时间|证券代码|证券名称|买0卖1|买卖标志|委托价格|委托数量|委托编号|成交价格|成交数量|成交金额|成交编号|股东代码|状态数字标识|状态说明"
    def __init__(self, backtester, money=1000000, date='2000-1-1 9:30:00'):
        """
        date: 开户日期
        """
        self.backtester = backtester
        self.money = money	#可用资金
        #因为下单即认为成交, 因此只需要成交记录
        self.df_ChengJiao = pd.DataFrame( columns=self.chengjiao_columns.split('|'))
        self.df_stock = pd.DataFrame( columns=self.stocklist_columns.split('|'))
        for col in '证券数量|库存数量|可卖数量'.split('|'):
            self.df_stock[col] = self.df_stock[col].astype(int)
        self.df_zhijing = pd.DataFrame(np.array([money,money,0,money,0])).T
        self.df_zhijing.columns = self.zhijing_columns.split('|')
        self.df_zhijing.index = pd.DatetimeIndex([date])
    def _T1(self, date):
        """经过了一天， 重置stock表可卖数量
        date: str datetime"""
        #判断最后一个委托与当前时间是不是隔天
        if len(self.df_ChengJiao) == 0:
            return
        last_date = self.df_ChengJiao['成交日期'][-1]
        cur_date = date.split(' ')[0]
        if cur_date != last_date:
            #重置可卖数量
            for i in range(len(self.df_stock)):
                self.df_stock.set_value(i,'证券数量', self.df_stock.iloc[i]['库存数量'])
                self.df_stock.set_value(i,'可卖数量', self.df_stock.iloc[i]['证券数量'])
    def _insertChengJiaoRecorde(self, code, price, num, date, bSell):
        #成交记录
        row = {}
        for k in self.chengjiao_columns.split('|'):
            row[k] = ''
        row['成交日期'] = date.split(' ')[0]
        row['成交时间'] = date.split(' ')[1]
        row['证券代码'] = code
        row['买0卖1'] = row['买卖标志'] = str(bSell)
        row['委托价格'] = row['成交价格'] = price
        row['委托数量'] = row['成交数量'] = num
        row['成交金额'] = float("%.2f"%(num*price))
        row['状态说明'] = '已成'
        self.df_ChengJiao.loc[len(self.df_ChengJiao)] = row
        self.df_ChengJiao.index = pd.DatetimeIndex(list(self.df_ChengJiao.index[:-1])+[date])
    def _updateStockChengBen(self, code, price, num, bSell):
        """更新买入成本"""
        #更新平均成本
        org_num = self.df_stock['库存数量'][self.df_stock['证券代码'] == code]
        org_price = self.df_stock['买入均价'][self.df_stock['证券代码'] == code]
        if not bSell:
            #买
            new_price = (org_num*org_price+num*price)/(org_num+num)
        else:
            #卖
            new_price = (org_num*org_price-num*price)/(org_num-num)
        self.df_stock['买入均价'][self.df_stock['证券代码'] == code] = new_price
        self.df_stock['当前价'][self.df_stock['证券代码'] == code] = price
    def _insertZhiJing(self,code, price, num, bSell, date):
        """添加资金记录, 余额|可用|参考市值|资产|盈亏
        余额|盈亏 暂时没有使用
        """
        m = price*num
        if bSell:
            self.money += m*(1-sxf())
        else:
            self.money -= m
        row = self.df_zhijing.iloc[-1].tolist()
        row[1] = self.money
        #市值
        #这里没有其它股票的价格， 因此只能知道当前股票的市值, 所以只能模拟一只股票的实时交易情况
        #如果要支持多个股票， 需要backtester提供价格查询接口
        row[2] = int(self.df_stock['库存数量'][self.df_stock['证券代码'] == code])*price
        row[3] = row[2]+row[1]    
        self.df_zhijing.loc[len(self.df_zhijing)] = row
        self.df_zhijing.index = pd.DatetimeIndex(list(self.df_zhijing.index[:-1])+[date])
    def _buy(self, code, price, num, date):
        self._T1(date)

        money = price * num
        if self.money < money:
            num = ShouShu(self.money / price)
        if num == 0:
            return 
        bSell = 0    
        self._insertChengJiaoRecorde(code, price, num, date, 0)
        #加入股票列表
        row = {}
        for k in self.stocklist_columns.split('|'):
            row[k] = ''
        row['证券代码'] = code
        for col in '证券数量|库存数量'.split('|'):
            row[col] = num
        row['可卖数量'] = 0
        for col in '买入均价|当前价'.split('|'):
            row[col] = price
        if (self.df_stock['证券代码'] == code).any():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")	
                self._updateStockChengBen(code, price, num, bSell)
                #更新股票列表
                #self.df_stock['证券数量'][self.df_stock['证券代码'] == code] += num
                self.df_stock['库存数量'][self.df_stock['证券代码'] == code] += num
        else:
            self.df_stock.loc[len(self.df_stock)] = row
        self._insertZhiJing(code, price, num, bSell, date)
    def _sell(self, code, price, num, date):
        self._T1(date)

        #查询能卖的数量
        if (self.df_stock['证券代码'] == code).any():
            bSell = 1
            can_sell_num = int(self.df_stock['可卖数量'][self.df_stock['证券代码'] == code])
            num = min(num, can_sell_num)
            if num <= 0:
                return
            self._insertChengJiaoRecorde(code, price, num, date, 1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")	
                self._updateStockChengBen(code, price, num, bSell)
                #更新数量
                self.df_stock['可卖数量'][self.df_stock['证券代码'] == code] -= num
                self.df_stock['库存数量'][self.df_stock['证券代码'] == code] -= num
                self._insertZhiJing(code, price, num, bSell, date)
                #如果卖空了，删除记录
                if int(self.df_stock['库存数量'][self.df_stock['证券代码'] == code]) == 0:
                    self.df_stock = self.df_stock[self.df_stock['证券代码'] != code]

    def Order(self, bSell, code, price, num):
        """委托, 本地账户假定所有的委托都会成交
        return: str 成功则返回委托id号， 失败返回空"""
        assert(num % 100 == 0)
        assert(num > 0)
        sId=''
        if num == 0 :
            return sId
        date = self.backtester.getCurTickTime()
        if bSell:
            return self._sell(code, price, num, date)
        else:
            return self._buy(code, price, num,date)
    def StockList(self):
        """return : df"""
        return self.df_stock
    def ZhiJing(self):
        """每次交易后对资金表加一条记录
        return: df 未处理余额"""
        return self.df_zhijing
    def ChengJiao(self):
        """return: df"""
        return self.df_ChengJiao
    def WeiTuoList(self):
        """return: df"""
        return self.df_ChengJiao
    def CheDanList(self):
        raise NotImplementedError("Implement Interface")
    def CheDan(self, code, weituo_id):
        raise NotImplementedError("Implement Interface")

    def Report(self, end_day, is_detail=False):
        if sys.version > '3':
            print('python 3 can not execute')
            return 
        import stock,myredis,mysql,agl
        #成交记录
        df = self.df_ChengJiao.loc[:,['成交价格','成交数量','买卖标志','证券代码']]
        #print df
        #输出交易记录到json，供iChat访问
        df.columns = ['price','num','flag','code']

        df['d'] = df.index.astype(str)
        df['d'] = df['d'].map(lambda x: str(dateutil.parser.parse(x) + \
                                            datetime.timedelta(minutes=5)))
        myredis.set_obj('backtest_trade', df)
        #原有的php需要使用json， 现在使用django， 可以废弃
        #f = open('E:/Apache/Apache/htdocs/stock/trade_training/trade.json','w')
        #json.dump(np.array(df).tolist(),f)
        #f.close()
        if is_detail:	
            agl.print_df(df)

        #计算股票市值, 暂时只能处理一只股票的情况
        shizhi = 0
        close = 0
        if len(self.df_stock)>0:
            code = self.df_stock.iloc[0]['证券代码']
            close = stock.getHisdatDataFrameFromRedis(code,'',end_day).iloc[-1]['c']
            num = self.df_stock.iloc[0]['库存数量']
            shizhi += float(close)*int(num)
        print(self.df_zhijing.tail(n=1))
        print('市值:%f,总资产:%f'%(shizhi, self.money+shizhi))
        #如果持股不动，现在的资金
        #取第一次交易后的可用资金
        if len(self.df_zhijing)>1:
            money = self.df_zhijing.iloc[1]['可用']
        else:
            money = self.df_zhijing.iloc[0]['可用']
        #第一次股票数量到现在的市值
        num = 0
        if len(self.df_ChengJiao)>0:
            num = self.df_ChengJiao.iloc[0]['成交数量']
        shizhi = num*close
        print('如果持股不动 市值:%f,总资产:%f'%(shizhi, money+shizhi))


class mytest(unittest.TestCase):
    def test_simple(self):
        print(agl.getFunctionName())
        account = LocalAcount(BackTesting())
        code = '300033'
        account._buy(code, 70.3, 3000, '2016-5-10 9:33:00')
        account._buy(code, 73.7, 3000, '2016-5-10 10:35:00')
        account._sell(code, 74, 4000, '2016-5-10 10:35:00')
        account._buy(code, 75, 9000, '2016-5-11 13:35:00')
        account._sell(code, 73.5, 4500, '2016-5-11 14:35:00')
        account._sell(code, 73.2, 4500, '2016-5-11 14:55:00')
        account._sell(code, 73.2, 4500, '2016-5-11 14:56:00')
        account._sell(code, 72.2, 4500, '2016-5-12 14:55:00')
        account._buy(code, 71.2, 500, '2016-5-12 14:57:00')
        account.Report('2016-5-12')
        print(account.ZhiJing())
    def test_multi(self):
        account = LocalAcount(BackTesting())
        code = '300033'
        account._buy(code, 70.3, 3000, '2016-5-10 9:33:00')
        account._buy('300059', 33.7, 3000, '2016-5-10 10:35:00')
        account._sell(code, 74, 4000, '2016-5-10 10:35:00')
        account._sell('300059', 33.7, 3000, '2016-5-10 13:35:00')
        account._buy(code, 75, 9000, '2016-5-11 13:35:00')
        account._sell('300059', 73.5, 4500, '2016-5-11 14:35:00')
        account._sell(code, 73.2, 4500, '2016-5-11 14:55:00')
        account._sell(code, 73.2, 4500, '2016-5-11 14:56:00')
        account._sell(code, 72.2, 4500, '2016-5-12 14:55:00')
        account._buy(code, 71.2, 500, '2016-5-12 14:57:00')
        account.Report('2016-5-12')
        return account
    def test_call(self):
        """调用"""
        account = LocalAcount(BackTesting())
        code = '300033'
        account.Order(0, code,70.3, 3000)
        account.Order(1, code,3, 3000)
        account.Order(0, code,4, 1000)
        print(account.StockList())
        print(account.WeiTuoList())
    def _test_to_mysql(self):
        account = self.test_multi()
        df = account.ZhiJing()
        df.index.name = 't'
        print(df.columns)
        db = mysql.Tc()
        df.columns = db.getZhiJinCols()+['yin_kui']
        db.save(df, tbl_name=mysql.Tc.enum.zhijin)
        df = account.ChengJiao()
        df = df.loc[:,['证券代码','买卖标志','成交数量','成交价格','成交金额','成交编号']]	
        df.columns = db.getChenJiaoCols()
        df.index.name = 't'
        df['trade_id'] = df['trade_id'].map(lambda x: np.random.randint(0,100000) )
        db.save(df, tbl_name=mysql.Tc.enum.chenjiao)
def main(args):
    unittest.main()

if __name__ == "__main__":
    args = sys.argv[1:]
    main(args)
