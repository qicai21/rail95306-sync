import pandas as pd
from browser import Browser


def test_query_sending_data():
    # 创建一个锦州分公司的bdrowser
    # 查询2022-12-1日当天的新台子发送车情况
    brs = Browser()
    brs.login('jzts')
    brs.query_trains('send', '2022-12-01', '2022-12-01')

    # 查到当日共发运2列，1列57车，1列58车
    df = pd.DataFrame(brs.query_data)
    group_count = df.groupby('fcsj')['ch'].count().to_list()
    assert group_count == [58, 57]

    # 57车的状态信息为： 全部完成（含义为：卸货完毕并从新台子发走)。
    time_1 = df.fcsj.unique()[0]
    train = brs.get_train(time_1)
    assert train['status']['当前状态'] == '全部完成'

    # 行驶记录共有17条信息
    # 行驶记录最后信息为：新台子 卸车完毕，时间：2022-12-02 07:57:55
    assert len(train['tracing_log']) == 17
    train['tracing_log'] == {'station': '新台子', 'time': '2022-12-02T07:57:55', 'status': '卸车完毕'}

    # 存进了数据库
    # 继续其他测试.
    assert 1 == 0, 'go on coding!'

    # sending cars, arriving cars, cars position and status

    # query car trisk info url: http://ec.95306.cn/api/scjh/track/qeryYdgjNew
    # method : post
    # data: {'ydid': <unknow long txt>}
    # headers['referer'] = 'http://ec.95306.cn/ydTrickDu?prams=' + <unknow long txt>