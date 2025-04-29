import base64
from datetime import datetime
import numpy as np
import pandas as pd
from pymongo import MongoClient
from browser import Browser

def get_time(time_series: pd.Series) -> pd.Timestamp:
    """如果是一组不同的时间,则返回最大(最后)的时间.如果其中有None,说明当前项目没进行完,返回None"""
    if time_series.isna().any():
        return None
    ptn = '%Y-%m-%d %H:%M:%S'
    # if len(time_series.unique()) == 1:
        # time_txt = time_series.unique()[0]
        # return datetime.strptime(time_txt, ptn)
    # else:
    time_s = time_series.apply(lambda x: datetime.strptime(x, ptn))
    return time_s.max()


class Train():
    def __init__(self, idx, data_df=None):
        self.idx = idx 
        self.tracing = True  # 是否要追踪
        self.cargo = None
        self.cars = None
        self.direction = None
        self.ydid_list = None
        self.containers = None
        self.fzhzzm = None
        self.dzhzzm = None
        self.status = (0, '空白预报')
        self.time_logs = dict()
        self.tracing_logs = None
        self.eta = None
        if data_df is None:
            return
        self.setup_with_df(data_df)
        
    def setup_with_df(self, data_df):
        self.cargo = data_df.hzpm.to_list()[0]
        self.direction = 'send' if data_df.fzhzzm.to_list()[0] == '高桥镇' else 'back'
        self.fzhzzm = data_df.fzhzzm.unique()[0]
        self.dzhzzm = data_df.dzhzzm.unique()[0]
        if not data_df.ch.isna().any():
            self.cars = data_df.ch.to_list()
            self.ydid_list = data_df.ydid.to_list()
        if not data_df.xh.isna().any():
            self.containers = []
            for pair in data_df.xh.to_list():
                self.containers.extend(pair.split('/'))
        self.update_time_logs(data_df)

    def update_time_logs(self, data_df, browser=None):
        if self.direction == 'send':
            nodes = {
                'zcddsj': (1, '发端迁入'),
                'zckssj': (2, '发端开始装车'),
                'zcwbsj': (3, '发端装车完毕'),
                'zcdcsj': (4, '发端迁出'),
                'fcsj': (5, '发车'),
                'dzsj': (6, '到站'),
                'xcddsj': (7, '到端迁入'),
                'xckssj': (8, '到端开始卸车'),
                'xcwbsj': (9, '到端卸完')
            }
        else:
            nodes = {
                'fcsj': (5, '发车'),
                'dzsj': (6, '到站'),
                'xcwbsj': (9, '到端卸完')
            }
        for node, status in nodes.items():
            if self.status == status:  # 根据已有状态跳过赋值
                continue
            time = get_time(data_df[node])
            if time is None:
                return
            self.time_logs[node] = time
            self.status = status  # eg: (5, '发车')
            if node == 'fcsj':
                self.fcsj = time
            if node == 'dzsj':
                self.dzsj = time

    def current_report(self):
        txt = f'发往{self.dzhzzm}的重' if self.direction == 'send' else f'从{self.fzhzzm}发出的空'
        msg = f'编号为{self.idx}的{txt}车列，共计{len(self.cars)}车/{len(self.containers)}箱.'
        msg += f'目前状态为: {self.status}'
        if self.status[0] >= 5:
            msg += f'发车时间: {self.fcsj}' 
        if self.status[0] >= 6:
            msg += f'到站时间: {self.dzsj}' 
        print('*'*40)
        print(msg)

    def report(self):
        """eg:
        No.1 重车 新台子 52车 [在途2022-11-25 04:30 出锦州, 预计到达时间]。
        """
        txt = 'No.' + str(self.idx)
        txt += f'发往{self.dzhzzm}的重' if self.direction == 'send' else f'从{self.fzhzzm}发出的空'
        txt += f' {len(self.cars)}车'
        if self.status[0] >= 4:
            txt += ' [在途 '
            txt += f"{self.tracing_logs[1]['station']} {self.tracing_logs[1]['time']} {self.tracing_logs[1]['status']}"
            txt += f' 预计到达时间{self.eta}'
            txt += ']'
        else:
            txt += f" [{self.status}]"
        print(txt)
        print('*'*40)
        
    def get_position_data(self, browser, only_check_first=True):
        """only_check_first: 是否只查询第一辆车，并将其作为全列信息"""
        if only_check_first:
            try:
                data = browser.get_tracing_position_by_ydid(self.ydid_list[0])
                self.tracing_logs = data
                self.eta = data[0]['eta']
                return True
            except ValueError as ex:
                raise ex
        else:
            mid = len(self.ydid_list) // 2
            pos_datas = []
            for i in [0, mid, -1]:
                try:
                    data = browser.get_tracing_position_by_ydid(self.ydid_list[i])
                except ValueError as ex:
                    raise ex
                pos_datas.append(data)
            p1 = pos_datas[0]
            if (p1[1] == pos_datas[1][1] and
                p1 [1]== pos_datas[2][1]):
                self.tracing_logs = p1
                self.eta = p1[0]['eta']
                return True
            print('本列车体首中尾车位置不一,位置信息如下:')
            print([d[1] for d in pos_datas])
            select = input('是否使用首车作为本列位置?1:是;2:否。') 
            if select == '1':
                self.tracing_logs = p1
                self.eta = p1[0]['eta']
                return True
            print('跳过位置更新.')
            return False

    def try_update_position(self, browser, only_check_first=True):
        """only_check_first: 是否只查询第一辆车，并将其作为全列信息"""
        if self.status[0] >= 4:
            self.get_position_data(browser, only_check_first)


class TrainManager():
    def __init__(self) -> None:
        self.trains = [] 
        self.idx_table = {}
        self.db_conn = "mongodb://localhost:27017"
        self.db_name = 'ts_business'
        self.db_collection = 'trains'

    def save(self):
        client = MongoClient(self.db_conn)
        db = client[self.db_name]
        car_collection = db[self.db_collection]

    def update(self, car_df):
        for (station, time), group in car_df.groupby(['dzhzzm', 'fcsj']):
            fz = group.fzhzzm.unique()[0]
            idx = self.get_top_available_idx(fz)
            self.trains.append(Train(idx, group))

    def get_top_available_idx(self, fzhzzm):
        idx_list = self.idx_table.get(fzhzzm)
        if idx_list:
            return idx_list[0]
        if self.idx_table == {}:
            new_idx = 1
        else:
            idx_values = np.array(list(self.idx_table.values()))
            new_idx = idx_values.max() + 1
        self.idx_table[fzhzzm] = [new_idx, ]
        return new_idx