# rail95306-sync

## 一、 数据字典

'uuid'
'ydid'
'xqslh'
'ysfs'
'ifdzlh'
'ifdzyd'
'zcrq'
'fzhzzm' # 发站名称
'dzhzzm' # 到站名称
'dztmism'
'fjm'
'djm'
'hzpm' # 货种品名
'fhdwmc'
'fhdwdm'
'shdwmc'
'zcddsj' # 装车抵达时间
'zckssj' # 装车开始时间
'zcwbsj' # 装车完毕时间
'zcdcsj' # 装车带出时间
'hph'  # 运单号（货票号）
'yf'
'zyf'
'ifbg'
'ch'  # 车号
'fccc' # 发车车次
'fcsj' # 发车时间
'dzcc' # 到站车次
'dzsj' # 到站时间
'xcddsj' # 卸车到达时间（入线）
'xckssj' # 卸车开始时间
'xcwbsj' # 卸车完毕时间
'xcdcsj' # 卸车带出时间
'dzjfrq' # 到站缴费日期
'fz'
'dzyxhz'
'fzyxhz'
'fzyx'
'ztgjjcend'
'ztgjend'
'czydid'
'clczbz'
'hwjs'
'dzsfh'
'sfpbh'
'czcx' # 车型号
'ifsetmm'
'ifsqdzbg'
'zffs'
'zfzt'
'zfsj'
'zfsjForExcel'
'zfje'
'tyrqzzt'
'tyrqzsj'
'cyrqzzt'
'cyrqzsj'
'ifydzf'
'bswjid'
'dzbgBswjid'
'ydqzzt'
'pm'
'dzyx'
'shdwdm'
'bgxshrdm'
'bgxshrmc'
'bgztgj'
'iftcbg'
'dzqmjg'
'wxpbz'
'wxpdm'
'wxppmhz'
'ditieguogui'
'crcbs'
'bszlhmmbs'
'sfszlhmm'
'hzbgbs'
'ch1'
'ch2'
'ch3'
'hqjc'
'hwmc'
'cyrqdzl'
'cyrqdjs'
'lhmm'
'zpsj'
'xh' # 箱号
'tyrjzsx'
'spfmc'
'nsrdz'
'nsrdh'
'nsrkhh'
'nsrzh'
'nsrsbh'
'tbfs'
'yjlc'
'yjxfh'
'pmms'
'fffs'
'jhtzzt'
'zthzzt'
'cs'
'xs'
'zzl'
'csxs'
'dzbgZtjgjc'
'slrq'
'slrxm'
'wslyyhz'

## 二、 轨迹数据字典

[{'uuid': None,
  'id': None,
  'aid': None,
  'operator': '新台子',
  'loadBurTime': None,
  'loadMorTime': None,
  'dataNum': 0,
  'message': '货物已卸车完毕。',
  'detail': '2022-12-05 00:55:14',
  'busiType': None,
  'sourceList': None,
  'czdz': '辽宁省 铁岭市 铁岭县',
  'tmism': '53918',
  'rptid': None},
 {'uuid': None,
  'id': None,
  'aid': None,
  'operator': '新台子',
  'loadBurTime': None,
  'loadMorTime': None,
  'dataNum': 0,
  'message': '货物已开始卸车。',
  'detail': '2022-12-05 00:05:56',
  'busiType': None,
  'sourceList': None,
...
  'busiType': None,
  'sourceList': None,
  'czdz': '辽宁省 葫芦岛市 连山区',
  'tmism': '51632',
  'rptid': None}]


## 用户登录 95306 的模拟流程

1. 用户打开 95306 首页，服务器会加载一项<"https://ec.95306.cn/js/app.0ab11d6af2095d6af1e2.js">，里边有一个生成 password 的 rsa 加密code的方法，通过检索“setPublicKey”可以找到这个方法，里边存着公钥。
2. 用户清空浏览器 cookie 后，在 95306 登录页面输入用户名和密码，进入图片验证环节。浏览器自动向 “https://ec.95306.cn/api/yhzx/slug/getSliderImg” 发送 POST 请求。该请求返回拼图的 base64 数据（可通过 cv2 渲染）、token等重要数据。
3. 浏览器自动发出checkUserLoginState请求。正常情况下，返回{msg: "OK", returnCode: "00200", data: true} 。若在开发设计过程中或错误使用登录功能过于频繁，账号封停 1 - 2 小时，该检验会返回账户封停状态。

## 程序处理步骤

1. 程序的`browser.py`中设置了`get_encrypt_rsa`方法。
2. 程序调用`login`方法，方法内部先调用`get_login_token`方法，获取 token 和拼图横坐标数据 X（通过`browse.find_white_block_x`方法处理拼图得到）。
3. 程序调用get_white_list_for_update_access_session方法，模拟浏览器的checkUserLoginState请求,验证用户登陆状态并更新`SESSION`信息，来源于返回响应的header。
   
