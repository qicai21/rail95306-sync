import pytest
from random import choices
import os
import json
import browser
import pandas as pd
from datetime import datetime
from urllib import parse
from unittest import mock
from pymongo import MongoClient
from browser import Browser


TEST_JSON_FILE = './test_headers.json'


def make_data_set(i, groups):
    fcsj_list = [
        '2022-12-01 01:48:21',
        '2022-12-01 12:48:21',
        '2022-12-01 21:48:21',
        ]
    i %= groups
    uuid = ''.join(choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=32))
    ydid = ''.join(choices('123456789', k=18))
    return {
        'uuid': uuid,
        'ydid': ydid,
        'xqslh': '202211TZ686886',
        'ysfs': '3',
        'ifdzlh': None,
        'ifdzyd': 'Y',
        'zcrq': '20221201',
        'fzhzzm': '高桥镇',
        'dzhzzm': '新台子',
        'dztmism': '53918',
        'fjm': '沈阳局',
        'djm': '沈阳局',
        'hzpm': '大豆',
        'fhdwmc': '营口铁晟海港物流有限公司锦州分公司',
        'fhdwdm': '3183910',
        'shdwmc': '国家粮食和物资储备局辽宁局三三0处',
        'zcddsj': '2022-11-30 21:48:21',
        'zckssj': '2022-12-01 04:30:33',
        'zcwbsj': '2022-12-01 13:31:12',
        'zcdcsj': '2022-12-01 13:45:50',
        'hph': 'GZDJD0026738',
        'yf': 193680,
        'zyf': None,
        'ifbg': 'N',
        'ch': '1741952',
        'fccc': '80401',
        'fcsj': fcsj_list[i],
        'dzcc': '80401',
        'dzsj': '2022-12-02 05:29:00',
        'xcddsj': '2022-12-02 22:00:38',
        'xckssj': '2022-12-02 22:20:47',
        'xcwbsj': '2022-12-02 23:01:10',
        'xcdcsj': '2022-12-02 23:30:52',
        'dzjfrq': '2022-12-02 23:01:28',
        'fz': 'GZD',
        'dzyxhz': '国家粮食和物资储备局辽宁局三三0处专用线',
        'fzyxhz': '锦州高天铁路有限责任公司专用铁路',
        'fzyx': '51632002',
        'ztgjjcend': '货物已交付',
        'ztgjend': '80',
        'czydid': '516322211303087932',
        'clczbz': '0',
        'hwjs': '2',
        'dzsfh': None,
        'sfpbh': None,
        'czcx': 'C70E',
        'ifsetmm': '0',
        'ifsqdzbg': 'N',
        'zffs': '3',
        'zfzt': '1',
        'zfsj': '2022-12-01 13:12:36',
        'zfsjForExcel': None,
        'zfje': 193680,
        'tyrqzzt': None,
        'tyrqzsj': None,
        'cyrqzzt': None,
        'cyrqzsj': None,
        'ifydzf': None,
        'bswjid': '4490d573d74a4782914c53fe10f0ef72',
        'dzbgBswjid': None,
        'ydqzzt': None,
        'pm': '1160001',
        'dzyx': '53918001',
        'shdwdm': '3022230',
        'bgxshrdm': None,
        'bgxshrmc': None,
        'bgztgj': None,
        'iftcbg': 'N',
        'dzqmjg': 'Y',
        'wxpbz': '0',
        'wxpdm': None,
        'wxppmhz': None,
        'ditieguogui': '0',
        'crcbs': '01',
        'bszlhmmbs': '0',
        'sfszlhmm': None,
        'hzbgbs': '0',
        'ch1': None,
        'ch2': None,
        'ch3': None,
        'hqjc': None,
        'hwmc': None,
        'cyrqdzl': 64.0,
        'cyrqdjs': None,
        'lhmm': '0',
        'zpsj': '2022-12-01 13:04:55',
        'xh': 'JZPU9019010/JZPU9010250',
        'tyrjzsx': '一口价SY220806a号;\n托运人未支付到站杂费;一口价SY220806a号; 实际收货人：九三集团铁岭大豆科技有限公司',
        'spfmc': '锦州高天铁路有限责任公司',
        'nsrdz': '锦州经济技术开发区南海路一段20号',
        'nsrdh': '0416-2673019',
        'nsrkhh': '工行锦州开发区支行',
        'nsrzh': '0708000119200065117',
        'nsrsbh': '912107001206017080',
        'tbfs': None,
        'yjlc': None,
        'yjxfh': 'SY220806a',
        'pmms': None,
        'fffs': '3',
        'jhtzzt': None,
        'zthzzt': None,
        'cs': '0',
        'xs': '2',
        'zzl': '64.00',
        'csxs': '2',
        'dzbgZtjgjc': None,
        'slrq': '2022-11-30 09:55:43',
        'slrxm': '赵飞',
        'wslyyhz': None}

MOCK_RESULT = {
    'msg': 'OK',
    'returnCode': '00200',
    'data': {
        'total': 200,
        'list': [make_data_set(i, 2) for i in range(100)]
    }
}

def set_up_headers_file(date_str=None):
    if not date_str:
       date_str = datetime.now().strftime('%Y-%m-%dT%H:%M')

    test_config = {
        'jzts': {
            'name': 'jzts',
            'refresh_time': date_str, 
            'session': 'SESSION=testsession1', 
            'token': 'test_token_1'
            },
        'newts': {
            'name': 'newts',
            'refresh_time': date_str, 
            'session': 'SESSION=testsession2', 
            'token': 'test_token_2'
            }
    }
    with open(TEST_JSON_FILE, 'w') as file:
        json.dump(test_config, file)

class MockResponse():
    headers = {
        'ntent-Type': 'application/json;charset=UTF-8',
        'Set-Cookie': 'SESSION=MOCKSESSION; Path=/; HttpOnly',
        }
    status_code = 200
    content = json.dumps(MOCK_RESULT).encode()


def mock_response(*args):
    return MockResponse()

class TestBrowser():
    def setup_class(self):
        browser.input = lambda x: 'new_session_from_console'  # type: ignore
        set_up_headers_file('2022-11-30T15:00')
        self.brs = Browser()
        self.brs.headers_config_file = TEST_JSON_FILE
        self.brs.db_name = 'unittests'
        self.brs.post = mock.Mock(side_effect=mock_response)

    @classmethod
    def teardown_class(cls):
        os.remove(TEST_JSON_FILE)
        client = MongoClient('mongodb://localhost:27017/')
        client.drop_database('unittests')

    def test_ask_for_new_session_if_expired(self):
        self.brs.setup_user('jzts')
        assert self.brs.session == 'new_session_from_console'

    def test_relogin_with_diff_user(self):
        self.brs.setup_user('newts')
        assert self.brs.user['unit_name'] == parse.quote('锦州新铁晟港口物流有限公司') # type: ignore


    def test_update_session_and_token_of_user_to_file(self):
        self.brs.setup_user('jzts')
        resp = self.brs.post_and_update_session('send', query_data={'type': 'test'})
        with open(TEST_JSON_FILE, 'rb') as file:
            data = json.load(file)
        assert data['jzts']['session'] == 'SESSION=MOCKSESSION'

    def test_browser_can_save_and_update_to_mongodb(self):
        self.brs.query_data = MOCK_RESULT['data']['list']
        for data in self.brs.query_data:
            if data['fcsj'] == '2022-12-01 12:48:21':
                data['dzsj'] = ''
        result = self.brs.update_to_mongo()
        
        client = MongoClient('mongodb://localhost:27017')
        db = client.unittests
        collection = db[self.brs.db_collection] 
        cur = collection.find()
        df = pd.json_normalize(cur)
        assert df.shape[0] == 100
        assert df.loc[df.fcsj == '2022-12-01 12:48:21']['dzsj'].unique()[0] == ''

        for data in self.brs.query_data:
            if data['fcsj'] == '2022-12-01 12:48:21':
                data['dzsj'] = '2022-12-03 05:29:00'
        self.brs.update_to_mongo()
        cur = collection.find()
        df = pd.json_normalize(cur)
        assert df.loc[df.fcsj == '2022-12-01 12:48:21']['dzsj'].unique()[0] == '2022-12-03 05:29:00'
  
    def test_can_get_data_counts_and_download_continoursly(self):
        self.brs.query_trains('send', '2022-12-02', '2022-12-03', '新台子')
        assert len(self.brs.query_data) == 200
    
    def test_brs_can_gether_data_by_train(self):
        time_1 = self.brs.query_data[0]['fcsj']
        train = self.brs.get_train(time_1)
        assert len(train['cars']) == 100