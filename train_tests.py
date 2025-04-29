import pandas as pd
import pytest
from trains import Train, TrainManager
    

@pytest.fixture
def car_df():
    cars = ["1638141", "1561416", "1649778", "1604855", "1772002", "1822381", "5731180", "1574095", "1575792"]
    car_df = pd.DataFrame({'ch': cars})
    car_df['hzpm'] = '大豆'
    car_df['ydid'] = None
    car_df['xh'] = 'ABC/EFG'
    car_df['zcddsj'] = '2022-12-14 23:00:00'
    car_df['zckssj'] = '2022-12-14 23:30:00'
    car_df['zcwbsj'] = '2022-12-14 23:50:00'
    car_df['zcdcsj'] = '2022-12-15 00:30:00'
    car_df['xcddsj'] = None
    car_df['fzhzzm'] = '高桥镇'
    car_df['dzhzzm'] = '新台子'
    car_df['fcsj'] = None
    car_df['dzsj'] = None
    car_df['fcsj'][0:3] = '2022-12-15 1:00:00'
    car_df['dzsj'][0:3] = '2022-12-15 15:00:00'
    car_df['fcsj'][3:6] = '2022-12-15 19:00:00'
    return car_df



def test_train_manager_can_create_new_train_no_with_train_df(car_df):
    mgr = TrainManager()
    mgr.update(car_df)
    assert mgr.trains[0].idx == 1
    assert mgr.trains[1].idx == 2
    assert mgr.trains[2].idx == 3

def test_can_auto_create_new_idx_by_station():
    mgr = TrainManager()
    idx = mgr.get_top_available_idx('高桥镇')
    assert idx == 1

def test_set_train_arrived(car_df):
    mgr = TrainManager()