from urllib import parse
import json

USERS = {
    'jzts': {
        "name": 'jzts',
        "unit_id":"3183910",
        "user_id":"3183910003",
        'user_pwd': 'Ts@95306',
        "user_name": parse.quote('魏庆凯'),
        "unit_name": parse.quote('营口铁晟海港物流有限公司锦州分公司')
    },
    'newts': {
        "name": "newts",
        "unit_id":"5035440",
        "user_id":"5035440021",
        'user_pwd': 'Xts@95306',
        "user_name": parse.quote('郭东北'),
        "unit_name": parse.quote('锦州新铁晟港口物流有限公司')
    }
}


def user_do_txt(user):
    data = {
    "userName": user['user_name'],
    "unitName": user['unit_name'],
    "unitTag": "291",
    "userId": user['user_id'],
    "bureauId": "T00",
    "bureauDm": "02",
    "userType": "OUTUNIT",
    "unitId": user['unit_id'],
    "type": "outer",
    "unitPropertiesList": ["fh"]
    }
    txt = str(data)
    url_chars = {"'": "%22", " ": "", ",": "%2C"}
    for k,v in url_chars.items():
        txt = txt.replace(k, v)
    return txt

def get_login_cookie(session):
    BIGipServerpool_1 = 'BIGipServerpool_wdlxx1=!O4DSnDTdLbZaUDKb/CULM79eIdI1FBgREw19tQsYtaOdLMLgtVZV0fSKN0Xhm3dDYS17WwzF3Q2wwA=='
    BIGipServerpool_2 = 'BIGipServerpool_wdlxx2=!htG+Jyg8oXZO9uCb/CULM79eIdI1FC8trHy3RS0sgs8Jr9b92z9D7Uz3GkeOOdKz3uoMTM/bkXqp+Q=='
    session_txt = session if session.startswith('SESSION') else 'SESSION='+session
    return '; '.join([BIGipServerpool_1, BIGipServerpool_2, session_txt])

def get_cookie(user, session, access_token): 
    # BIGip两项配置貌似可以省略
    BIGipServerpool_1 = 'BIGipServerpool_wdlxx1=!O4DSnDTdLbZaUDKb/CULM79eIdI1FBgREw19tQsYtaOdLMLgtVZV0fSKN0Xhm3dDYS17WwzF3Q2wwA=='
    BIGipServerpool_2 = 'BIGipServerpool_wdlxx2=!htG+Jyg8oXZO9uCb/CULM79eIdI1FC8trHy3RS0sgs8Jr9b92z9D7Uz3GkeOOdKz3uoMTM/bkXqp+Q=='

    userdo = '95306-1.6.10-userdo=' + user_do_txt(user)
    cookie_access_token = '95306-1.6.10-accessToken=' + access_token
    session_txt = session if session.startswith('SESSION') else 'SESSION='+session
    return '; '.join([BIGipServerpool_1, BIGipServerpool_2, cookie_access_token, userdo, session_txt])

def get_headers(user):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,de;q=0.5",
        "bureauDm": "02",
        "bureauId": "T00",
        "channel": "P",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "DNT": "1",
        "Host": "ec.95306.cn",
        "Origin": "http://ec.95306.cn",
        "type": "outer",
        "unitId": user['unit_id'],
        "unitName": user['unit_name'],
        "userId": user['user_id'],
        "userName": user['user_name'],
        "userType": "OUTUNIT",
        "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
    }
    return headers


def make_query_data(start_date_txt:str, end_date_txt:str, page_num, direction, station) -> str:
    '''如果station为all,direct为back,则fztmism为空,反之亦然.'''
    station_no = {'新台子': '53918', '得胜台': '53924', '虎石台': '53900', 'all':''}
    if direction == 'back':
        fztmism = station_no[station]
        dztmism = '51632'
        query_data = {
            "zcqsrq":start_date_txt,
            "zcjzrq":end_date_txt,
            "pm": "9800001",
            "hph":"",
            "xqslh":"",
            "ydid":"",
            "fztmism":fztmism,
            "dztmism":dztmism,
            "ysfs":"",
            "shdwdm":"",
            "shdwmc":"",
            "ydztgj":"",
            "queryFlag":"1",
            "pageSize":100,
            "pageNum":page_num,
            "qzzt":"",
            "ifszlhr":"",
            "ifdzyd":"",
            "zfzt":"",
            "njfzt":"",
            "ch":"",
            "ddrqStart":"",
            "ddrqEnd":"",
            "xcsjStart":None,
            "xcsjEnd":None,
            "zpsjqsrq":"",
            "zpsjjzrq":"",
            "xh":"",
            "orderBy":"",
            "orderMode":""
        }
    elif direction == 'send':
        fztmism = '51632'
        dztmism = station_no[station]
        query_data = {
            "ydtbqsrq":"",
            "ydtbjzrq":"",
            "zcqsrq":start_date_txt, # 装车起始日期
            "zcjzrq":end_date_txt, # 装车截至日期
            "xqslh":"",
            "ydid":"",
            "dztmism": dztmism, # 到站编码
            "fztmism": fztmism,
            "pm": "1160001",
            "ysfs":"",
            "shdwmc":"",
            "shdwdm":"",
            "ydztgj":"",
            "pageSize":100,
            "pageNum": page_num,
            "ifdzyd":"",
            "ifsetmm":"",
            "zfzt":"",
            "zffs":"",
            "dzqmjg":"",
            "ifkszlhmm":"",
            "ch":"",
            "hph":"",
            "zpsjqsrq":"",
            "zpsjjzrq":"",
            "yjxfh":"",
            "xh":"",
            "zcrbjhuuid":"",
            "orderBy":"",
            "orderMode":""}
    else:
        raise KeyError('流向参数错误')
    return json.dumps(query_data)

login_headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    # 'Content-Length': '328',
    'Content-Type': 'application/json',
    'Cookie': 'BIGipServerpool_wdlxx1=!O4DSnDTdLbZaUDKb/CULM79eIdI1FBgREw19tQsYtaOdLMLgtVZV0fSKN0Xhm3dDYS17WwzF3Q2wwA==; BIGipServerpool_wdlxx2=!htG+Jyg8oXZO9uCb/CULM79eIdI1FC8trHy3RS0sgs8Jr9b92z9D7Uz3GkeOOdKz3uoMTM/bkXqp+Q==; SESSION=NjU3NjkyOGMtMjQ5ZS00N2JjLTgzNzQtOWM0NDkyMWQyN2I4',
    'Host': 'ec.95306.cn',
    'Origin': 'https://ec.95306.cn',
    'Referer': 'https://ec.95306.cn/login',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'channel': 'P',
    'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'type': 'outer'
}