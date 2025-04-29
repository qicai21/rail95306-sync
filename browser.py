import requests
import json
import base64
import pandas as pd
import numpy as np
import cv2
from datetime import datetime
from pymongo import MongoClient
from header_configs import USERS, get_cookie, make_query_data, \
    get_headers, login_headers, get_login_cookie

PATTN = '%Y-%m-%dT%H:%M'


URLS = {
    'send': {
        'url': 'http://ec.95306.cn/api/scjh/wayBillQuery/queryCargoSend',
        'referer': 'http://ec.95306.cn/loading/goodsQuery'},
    'back': {
        'url': 'http://ec.95306.cn/api/scjh/wayBillQuery/queryCargoArrival',
        'referer': 'http://ec.95306.cn/deliveryService/arrivalReceiptQuery'},
    'refresh_access_token': {
        'url': 'http://ec.95306.cn/api/scjh/wayBillQuery/queryCargoSend',
        'referer': 'http://ec.95306.cn/loading/goodsQuery'},
    'query_pos': {
        'url':  'https://ec.95306.cn/api/scjh/track/qeryYdgjNew',
        'referer': 'https://ec.95306.cn/ydTrickDu?prams='},
}


def readb64(base64_string):
    image_data = base64.b64decode(base64_string)
    nparr = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return image

def find_white_block_x(base64_string):
    image = readb64(base64_string)
    # 转换为灰度图像
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 二值化处理
    _, binary = cv2.threshold(gray, 253, 255, cv2.THRESH_BINARY)  # 阈值200可根据实际情况调整
    h, w = binary.shape

    # 遍历图像，寻找5x5的白色方块
    for y in range(0, h - 40):
        for x in range(0, w - 40):
            # 提取40x8的区域
            block = binary[y:y + 5, x:x + 44]
            # 检查是否为全白色
            if cv2.countNonZero(block) == 220:  # 5x5全白色像素点数为25
                return x

    print("未找到符合条件的白色方块")
    return None

class Browser():
    def __init__(self, user=None):
        self.repeat = 3
        self.headers_config_file = 'my_95306_headers.json'
        self.db_conn = 'mongodb://127.0.0.1:27017'
        self.db_name = 'ts_business'
        self.db_collection = 'cars'
        self.query_data = []
        if user:
            self.setup_user(user)

    def setup_user(self, user):
        self.user = USERS.get(user)
        if self.user is None:
            raise KeyError('不存在的user')
        self.reset_headers_with_user()

    def reset_headers_with_user(self):
        self.headers = get_headers(self.user)
        with open(self.headers_config_file, 'rb') as file:
            config = json.load(file)
        user_data = config[self.user['name']]
        self.session = user_data['session']
        self.token = user_data['token']
        self.refresh_token = user_data['refresh_token']

        last_refresh = datetime.strptime(user_data['refresh_time'], PATTN)
        t_ = datetime.now() - last_refresh
        if t_.total_seconds() / 60 / 60 > 24:
            self.ask_for_new_session()

        cookie = get_cookie(self.user, self.session, self.token)
        self.headers.update({
            'access_token': self.token,
            'Cookie': cookie,
        })


    def ask_for_input_token(self):
        self.token = input('请输入token:')
        cookie = get_cookie(self.user, self.session, self.token)
        self.headers.update({'Cookie': cookie})
        self.update_and_save_to_local()

    def update_and_save_to_local(self):
        date_txt = datetime.now().strftime(PATTN)
        with open(self.headers_config_file, 'r+') as file:
            data = json.load(file)
            user = self.user['name']
            data[user].update({
                "refresh_time": date_txt,
                "session": self.session,
                "token": self.token,
                "refresh_token": self.refresh_token
            })
            file.seek(0)
            json.dump(data, file, ensure_ascii=False)
            file.truncate()

    def post_after_setup_headers(self, url, query_data):
        resp = requests.post(url, query_data, headers=self.headers)
        if resp.status_code != 200:
            self.refresh_access_token()
        resp = requests.post(url, query_data, headers=self.headers)
        if resp.status_code != 200:
            raise ValueError('查询失败：' + resp.content.decode())
        return resp

    def post_and_update_and_save_to_local(self, direction, query_data, **kwargs):
        content_length = str(len(str(query_data)))
        url = URLS[direction]['url']
        referer = URLS[direction]['referer']
        if direction == 'query_pos':
            referer += kwargs['ydid_encode']
        self.headers.update({
            'Content_Length': content_length,
            'Referer': referer
        })
        resp = self.post_after_setup_headers(url, query_data)
        print(resp)
        if resp.status_code == 200:
            self.session = resp.headers['Set-Cookie'].split(';')[0]
            self.update_and_save_to_local()
        return resp.content.decode()

    def run_post_loops(self, date_start, date_end, direction, station):
        remaining = 1
        page_num = 0
        while remaining > 0:
            page_num += 1
            query_data = make_query_data(date_start, date_end, page_num, direction, station)
            resp = self.post_and_update_and_save_to_local(direction, query_data)
            data = json.loads(resp)
            ttl = data['data']['total']
            remaining = ttl - page_num * 100
            self.query_data.extend(data['data']['list'])

    def query_trains(self, direction:"send or back", date_start:"formating 2022-11-03", date_end:"formating 2022-11-03", station)->list:
        self.query_data = []
        self.run_post_loops(date_start, date_end, direction, station)

    def update_to_mongo(self):
        client = MongoClient(self.db_conn)
        db = client[self.db_name]
        car_collection = db[self.db_collection]
        df = pd.DataFrame(self.query_data)
        df = df.rename(columns={'uuid': '_id'})
        for index, row in df.iterrows():
            car_collection.find_one_and_delete({'_id': row['_id']})
        car_collection.insert_many(df.to_dict('records'))

    def get_train(self, send_time):
        df = pd.DataFrame(self.query_data)
        cars_df = df.loc[df.fcsj == send_time]
        train = {
            'fcsj': send_time,
            'cars': cars_df.ch.to_list()
        }
        return train

    def refresh_access_token(self):
        refresh_token_url = 'https://ec.95306.cn/api/zuul/refreshToken'
        data = {'extData': {'grant_type': "refresh_token", 'refresh_token': self.refresh_token}}
        cookie = get_cookie(self.user, self.session, self.token)
        query_data =json.dumps(data)
        content_length = str(len(str(query_data)))
        referer = 'http://ec.95306.cn/loading/goodsQuery'
        self.headers.update({
            'Content_Length': content_length,
            'access_token': self.token,
            'Cookie': cookie,
            'Referer': referer
        })
        resp = self.post_after_setup_headers(refresh_token_url, query_data)
        if resp.status_code != 200:
            self.ask_for_input_token()
            return
        read_data = json.loads(resp.content.decode())
        self.token = read_data['data']['accessToken']
        self.refresh_token = read_data['data']['refreshToken']
        self.update_and_save_to_local()

    def auto_udpate(self, start_date, station='all'):
        """如果station为'all', 则查找所有货名为大豆,发站是高桥镇,和货名为集装箱,到站是高桥镇的。"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            self.query_trains('send', start_date, today, station)
            send_count = len(self.query_data)
            if send_count > 0:
                self.update_to_mongo()
            self.query_trains('back', start_date, today, station)
            back_count = len(self.query_data)
            if back_count > 0:
                self.update_to_mongo()
            print(f'ttl {send_count} sending and {back_count} backing data update completed.')
        except Exception as ex:
            raise ex
            
    def login(self, rsa_pwd):
        token, pos = self.get_login_token()
        self.get_white_list_for_update_access_session()
        url = 'https://ec.95306.cn/api/zuul/login'
        data = {
            "userName": self.user['user_id'],
            "type":"outer",
            "x": pos,
            "token": token,
            "secType":"RSA",
            "extData":{"grant_type":"password"}
            }
        data['password'] = rsa_pwd
        post_data = json.dumps(data)

        content_length = len(post_data)
        cookie = get_login_cookie(self.session)
        self.login_headers = login_headers.copy()
        self.login_headers['Content-Length'] = str(content_length)
        self.login_headers['Cookie'] = cookie

        resp = requests.post(url, post_data, headers=self.login_headers)
        resp_data = resp.content.decode()
        login_data = json.loads(resp_data)
        if login_data['msg'] != 'OK':
            raise ValueError('登录失败:' + resp_data)
        self.token = login_data['data']['accessToken'] 
        self.refresh_token = login_data['data']['refreshToken']
        self.update_and_save_to_local()

    def get_login_token(self):
        token_url = 'https://ec.95306.cn/api/yhzx/slug/getSliderImg'
        resp = requests.post(token_url, '{}', headers=login_headers)
        data = json.loads(resp.content.decode())['data']
        token = data['token']

        pos_x = find_white_block_x(data['oriCopyImage'])
        if pos_x is None:
            raise ValueError('未找到白色方块')
        return [token, pos_x]

    def get_white_list_for_update_access_session(self):
        url = 'https://ec.95306.cn/api/yhzx/user/queryWhiteListStatus'
        post_data = '{"userId":%s}'%self.user['user_id']
        resp = requests.post(url, data=post_data, headers=login_headers)
        self.session = resp.headers['Set-Cookie'].split(';')[0]
        self.update_and_save_to_local()

    def get_tracing_position_by_ydid(self, ydid):
        ydid_ = ydid.encode()
        for i in range(6):
            ydid_ = base64.b64encode(ydid_)
        ydid = ydid_.decode()
        data = {'ydid': ydid}
        post_data = json.dumps(data)
        ydid_encode = ydid.replace('=', '%3D')
        resp = self.post_and_update_and_save_to_local('query_pos', post_data, ydid_encode=ydid_encode)
        data = json.loads(resp)
        result = [{'eta': data['data']['yjddsj']},]  # yjddsj是预计到到时间,这个发车了就不变了,仅供参考
        for d in data['data']['gj']:
            d_ = {}
            d_['station'] = d['operator']
            d_['time'] = d['detail']
            d_['status'] = d['message']
            result.append(d_)
        return result