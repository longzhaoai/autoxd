#-*- coding:utf-8 -*-
# Copyright (c) Kang Wang. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# QQ: 1764462457

#把主目录放到路径中， 这样可以支持不同目录中的库
import os


"""在线策略入口"""
import numpy as np
import sys
import help,agl,enum,stock
import backtest_policy

class BackTestPolicy:
    """回测入口"""
    class enum:
        tick_mode = 0           #每个tick都处理
        hisdat_mode = 1         #只处理日线，close
    def __init__(self, mode=0):
        self.policys = []
        self.mode = mode    #回测模式
    def Regist(self, policy):
        """添加策略"""
        self.policys.append(policy)
    def Run(self, start_day, end_day, is_report=False):
        #try:
            #数据初始化, 生成数据面板
            days = (start_day, end_day)
            hisdat_start_day = help.MyDate.s_Dec(start_day, -100)
            self.panel_hisdat = stock.DataSources.getHisdatPanl(self.codes, 
                                                                (hisdat_start_day, end_day))
            fenshi_start_day = help.MyDate.s_Dec(start_day, -5)
            fenshi_days = (fenshi_start_day, help.MyDate.s_Dec(end_day, 1))
            self.dict_fenshi = stock.DataSources.getFenshiPanl(self.codes, fenshi_days)
            self.panel_fiveminHisdat = stock.DataSources.getFiveMinHisdatPanl(\
                self.codes, fenshi_days)   
            for policy in self.policys:
                policy.data.set_datasource(self.panel_hisdat, self.dict_fenshi, \
                                           self.panel_fiveminHisdat)
            #按照天来排
            #self._TravlDay('2014-5-1','2015-8-1')
            self._OnFirstRun(start_day)
            self._TravlDay(start_day, end_day)
            #生成一份收盘价给统计用
            list_closes = []
            for code in self.codes:
                df = self.panel_hisdat[code]
                list_closes.append((code, df.ix[-1]['c']))
            #输出账号结果
            for policy in self.policys:
                if 0: policy = qjjy.Strategy(data)
                #policy.get().account.Report()
                policy.Report(start_day, end_day)
        #except Exception as e:
            #print str(e)
    def _IsKaiPan(self, code, day):
        """判断当前天是否开盘"""
        kline = stock.Kline(code,day,day)
        return len(kline.hisdats)>0
    def _OnFirstRun(self, start_day):
        """允许策略在开始前有一个事件"""
        ts = range(570,690) + range(779, 900+1)
        for code in self.codes:
            for strategy in self.policys:
                if self.mode == self.enum.tick_mode:
                    #分时遍历, 按分钟走
                    if hasattr(strategy, 'OnFirstRun'):
                        strategy.data.set_code(code, start_day, ts[0])
                        strategy.OnFirstRun()
                if self.mode == self.enum.hisdat_mode:
                    if hasattr(strategy, 'OnFirstRun'):
                        strategy.data.set_code(code, start_day, ts[0])
                        strategy.OnFirstRun()                
    def _TravlTick(self, day):
        ts = [[570,690],[779,900]]
        ts = range(570,690) + range(779, 900+1)
        #按照分钟来遍历
        for code in self.codes:
            #print code
            if not self._IsKaiPan(code, day):
                continue
            for strategy in self.policys:
                df = self.dict_fenshi[code].ix[day] #以时间为索引
                #fenshi_length = len(df) #只迭代当天的
                if self.mode == self.enum.tick_mode:
                    #分时遍历, 按分钟走
                    for t in ts:
                        strategy.data.set_code(code, day, t)
                        strategy.Run()
                if self.mode == self.enum.hisdat_mode:
                    strategy.data.set_code(code, day, 900)
                    strategy.Run()
    def _TravlDay(self, start_day, end_day):
        """遍历天， 开始时间， 结束时间"""
        #为了只读一次数据库, 先把日线读了
        for code in self.codes:
            for strategy in self.policys:
                #回测前先清除一下上次产生的cache
                import strategy.qjjy
                strategy.qjjy.Qjjy_accout.DelSerial(code)                
        start_day = help.MyDate(start_day)
        #start_day.Add(3)    #否则取昨收盘会失败
        end_day = help.MyDate(end_day)
        while True:
            day = start_day.ToStr()
            #print day
            self._TravlTick(day)
            if start_day.Next() > end_day.GetDate():
                break
    def SetStockCodes(self, codes):
        """对这些codes进行回测"""
        self.codes = codes
    @staticmethod
    def Test():
        print(u'入口由策略自身执行')
        
def main(args):
    agl.tic()
    BackTestPolicy.Test()
    agl.toc()
    print "end"
    
if __name__ == "__main__":
    try:
        args = sys.argv[1:]
        main(args)
    except:
        main(None)