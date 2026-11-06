# -*- coding: utf-8 -*-
"""抓取交通银行 / 交银理财官网公开产品清单，生成 bcm.js。

接口：POST https://www.bankcomm.com/SITE/queryFundInfoListNew.do
  body: REQ_MESSAGE=<urlencoded JSON>；JSON = {REQ_HEAD:{TRAN_PROCESS:'',TRAN_ID:''}, REQ_BODY:{start,pageSize}}
  返回 RSP_BODY.fundInfoList（pageSize 可到 500，start 递增到空为止，共约 2520 只）

字段要点：
  fundlevel 1R/2R/3R -> R1/R2/R3；displayrate + displayratedescription = 当前展示的年化/基准；
  displayrate 也可能是公式挂钩型（含中文/指数），此时退回 sincerateyear / expectyearincomeratio；
  官网列表不披露近1月区间收益，ret_1m 留空（不臆造）。
"""
import json, re, os, ssl, sys, time, datetime, urllib.request, urllib.parse

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

D = os.path.dirname(os.path.abspath(__file__))
API = 'https://www.bankcomm.com/SITE/queryFundInfoListNew.do'
DETAIL = ('https://m.bankcomm.com/BankCommSite/shtml/jyjr/cn/7226/7266/7281/7282/'
          '41841.shtml?channelId=7226&code=')
HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://www.bankcomm.com/BankCommSite/jyjr/cn/lcpd/fundsList.html'}
CTX = ssl.create_default_context()
CTX.options |= 0x4
TODAY = datetime.date.today().isoformat()
DD_MAP = {'R1': 0.1, 'R2': 0.5, 'R3': 1.5, 'R4': 3.0, 'R5': 5.0}


def query(start, size=500):
    req = {'start': str(start), 'pageSize': str(size)}
    msg = json.dumps({'REQ_HEAD': {'TRAN_PROCESS': '', 'TRAN_ID': ''}, 'REQ_BODY': req}, ensure_ascii=False)
    body = urllib.parse.urlencode({'REQ_MESSAGE': msg}).encode()
    last = None
    for _ in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(API, data=body, headers=HDRS), timeout=30, context=CTX)
            d = json.loads(r.read().decode('utf-8', 'ignore'))
            return (d.get('RSP_BODY') or {}).get('fundInfoList') or []
        except Exception as e:
            last = e
            time.sleep(0.8)
    print('WARN query failed at start', start, last, flush=True)
    return []


def fetch_all():
    out, start = [], 0
    for i in range(12):
        ls = query(start)
        print(f'page {i+1}: start={start} +{len(ls)} (total {len(out)+len(ls)})', flush=True)
        out.extend(ls)
        if len(ls) < 500:
            break
        start += 500
    seen, uniq = set(), []
    for x in out:
        c = x.get('fundcode')
        if c and c not in seen:
            seen.add(c)
            uniq.append(x)
    return uniq


def parse_rate(s):
    """纯数字百分比 -> (min,max)；公式型/异常 -> None"""
    if not s:
        return None
    s = str(s).strip()
    if re.search(r'[\u4e00-\u9fff]|指数|中债|点击查看|\+', s, re.I):
        return None
    m = re.fullmatch(r'([\d.]+)\s*%\s*[-~至]\s*([\d.]+)\s*%', s)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 0 <= a <= 15 and 0 <= b <= 15 and a <= b:
            return (a, b)
        return None
    m = re.fullmatch(r'([\d.]+)\s*%', s)
    if m:
        a = float(m.group(1))
        return (a, a) if 0 <= a <= 15 else None
    return None


def fmt_date(s):
    s = str(s or '').strip()
    return f'{s[:4]}-{s[4:6]}-{s[6:8]}' if re.fullmatch(r'\d{8}', s) else None


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def zero_int(s):
    try:
        n = int(str(s).strip())
        return n if n > 0 else None
    except Exception:
        return None


def term_from_desc(s):
    s = str(s or '')
    m = re.search(r'(\d+)\s*天', s)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*年', s)
    if m:
        return int(m.group(1)) * 365
    m = re.search(r'(\d+)\s*个月', s)
    if m:
        return int(m.group(1)) * 30
    if '每日' in s or '日开' in s or '灵活赎' in s:
        return 0
    return None


def strip_none(d):
    return {k: v for k, v in d.items() if v is not None}


def build(it, idx):
    code = str(it.get('fundcode') or '')
    risk = {'1R': 'R1', '2R': 'R2', '3R': 'R3', '4R': 'R4', '5R': 'R5'}.get(str(it.get('fundlevel')), 'R3')
    desc = (it.get('displayratedescription') or '').strip()
    rate = parse_rate(it.get('displayrate'))
    fallback = to_float(it.get('sincerateyear')) or to_float(it.get('expectyearincomeratio'))
    perf = perf_type = perf_mid = None
    if rate:
        a, b = rate
        perf = f'{a}%~{b}%' if a != b else f'{a}%'
        perf_type = desc or '最新年化'
        perf_mid = round((a + b) / 2, 3)
    elif fallback is not None and 0 < fallback <= 15:
        perf = f'{fallback}%'
        perf_type = '成立以来年化'
        perf_mid = fallback

    subs, bids = str(it.get('subsflg')), str(it.get('bidsflg'))
    if subs == '1':
        st_code, st_name = '02', '认购中'
    elif bids == '1':
        st_code, st_name = '01', '申购中'
    else:
        st_code, st_name = '05', '已售完'

    est = fmt_date(it.get('setupdate'))
    age_years = None
    if est:
        try:
            age_years = round((datetime.date.today() - datetime.date.fromisoformat(est)).days / 365.25, 2)
        except Exception:
            pass
    td = term_from_desc(it.get('investdaydesc'))
    return strip_none({
        'id': idx,
        'name': (it.get('fundname') or '').strip(),
        'risk': risk,
        'type': '理财',
        'issuer': (it.get('registername') or '交银理财有限责任公司').strip(),
        'src': 'live',
        'status_code': st_code,
        'status': st_name,
        'public_flag': '公募',
        'detail_url': DETAIL + code,
        'perf': perf,
        'perf_type': perf_type,
        'perf_dt': '',
        'perf_mid': perf_mid,
        'nav': None,
        'nav_dt': None,
        'yield_min': rate[0] if rate else None,
        'yield_max': rate[1] if rate else None,
        'yield_mid': perf_mid,
        'yield_source': 'bcm_api' if perf_mid is not None else None,
        'yield_date': None,
        'ret_1m': None,
        'ret_1m_est': False,
        'term_days': td,
        'term_label': (it.get('investdaydesc') or it.get('investtermshow') or '').strip() or None,
        'min_amount': zero_int(it.get('minbidsamountbyindi')),
        'start_date': fmt_date(it.get('ipostartdate')),
        'end_date': fmt_date(it.get('fundenddate')),
        'open_date': None,
        'age_years': age_years,
        'guaranteed': False,
        'private': str(it.get('privateflg')).lower() == 'true',
        'est_drawdown': DD_MAP.get(risk, 1.0),
        'sales_target': None,
        'note': '交通银行官网理财频道；收益为官网披露的区间年化/七日年化/业绩比较基准，该列表未提供近1月收益。',
        'prod_code': code,
        'prod_status': it.get('fundstatus'),
    })


def main():
    items = fetch_all()
    print('products =', len(items), flush=True)
    products = [build(it, i + 1) for i, it in enumerate(items)]
    for k in ['perf', 'perf_mid', 'min_amount', 'term_days', 'ret_1m']:
        print(f'  {k}: {sum(1 for p in products if p.get(k) is not None)}', flush=True)
    meta = {'source': '交通银行官网理财频道 / 交银理财（免登录 queryFundInfoListNew）',
            'data_date': TODAY, 'live_date': TODAY, 'fetched_at': TODAY,
            'count': len(products), 'bank': '交通银行'}
    with open(os.path.join(D, 'bcm.js'), 'w', encoding='utf-8') as f:
        f.write('window.BCM_DATA = ')
        json.dump({'meta': meta, 'products': products}, f, ensure_ascii=False)
        f.write(';\n')
    print('bcm.js bytes =', os.path.getsize(os.path.join(D, 'bcm.js')), flush=True)


if __name__ == '__main__':
    main()
