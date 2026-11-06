# -*- coding: utf-8 -*-
"""抓取北银理财（北京银行理财产品）官网免登录数据，生成 bob.js 供多银行 App 切换加载。

数据链路（全部免登录、无 Referer/Cookie 校验）：
  1) GET /bylc-api/product/search?pageSize=500&pageNumber=N  -> 全量产品（父产品，约 1359 只）
  2) GET /bylc-api/product/subs?PROD_CODE=<父代码>            -> 子份额（A/F/M...），PROD_FLAG=1 时才有
  3) GET /bylc-api/product/perform?PROD_CODE=<子代码>         -> 官方过往业绩：MONTHINC(近1月年化%)/INC(成立以来年化%)/NAV/NAV_DATE

口径说明：
  - MONTHINC 是【年化】值，近1月实际收益 = MONTHINC * 区间天数 / 365（与官网净值反算一致）。
  - 业绩比较基准只接受纯数字百分比（区间/单值）；公式挂钩型（含"指数/中债/x"）不用数字冒充。
  - 卡片以父产品为单位，业绩取首个子份额（通常 A 类），已在 note 中标注。

输出：bob.js = window.BOB_DATA = {meta, products}；bob_raw.json 为原始快照（.gitignore）。
"""
import json, re, ssl, sys, os, time, datetime, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

D = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://www.beijingbobwealth.com.cn'
DETAIL = BASE + '/products_index/index.html?PROD_CODE='
HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}
CTX = ssl.create_default_context()
CTX.options |= 0x4  # OP_LEGACY_SERVER_CONNECT：老站 TLS 重协商兼容
TODAY = datetime.date.today().isoformat()

RISK_MAP = {'01': 'R1', '02': 'R2', '03': 'R3', '04': 'R4', '05': 'R5'}
STATUS_MAP = {'01': ('04', '预售'),      # 即将发售
              '02': ('02', '认购中'),    # 募集期
              '03': ('01', '申购中'),    # 存续期
              '04': (None, None)}        # 产品到期（不展示状态）
DD_MAP = {'R1': 0.1, 'R2': 0.5, 'R3': 1.5, 'R4': 3.0, 'R5': 5.0}


def api(path, **kw):
    q = {'noCache': str(int(time.time() * 1000))}
    q.update({k: v for k, v in kw.items() if v is not None})
    url = BASE + path + '?' + urllib.parse.urlencode(q)
    last = None
    for _ in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=25, context=CTX)
            return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(0.6)
    return {'ERR': str(last)}


def fetch_all():
    out, page = [], 1
    while True:
        d = api('/bylc-api/product/search', pageSize=500, pageNumber=page)
        data = (d.get('data') or {})
        lst = data.get('list') or []
        out.extend(lst)
        print(f'search page {page}: +{len(lst)} (total {len(out)}/{data.get("totalRow")})', flush=True)
        tp = int(data.get('totalPage') or 0)
        if not lst or (tp and page >= tp) or page >= 20:
            break
        page += 1
    # 去重
    seen, uniq = set(), []
    for x in out:
        c = x.get('PROD_CODE')
        if c and c not in seen:
            seen.add(c)
            uniq.append(x)
    return uniq


def enrich(it):
    """存续期产品：取首个子份额的官方业绩；其余产品跳过请求（不可能有历史业绩）。"""
    res = {'sub_code': None, 'MONTHINC': None, 'INC': None, 'NAV': None,
           'NAV_DATE': None, 'MONTHINC_START_DATE': None}
    if str(it.get('PROD_STATUS')) != '03':
        return res
    code = it.get('PROD_CODE')
    sub = code
    if str(it.get('PROD_FLAG')) == '1':
        s = api('/bylc-api/product/subs', PROD_CODE=code)
        subs = s.get('data') or []
        if isinstance(subs, list) and subs:
            # 优先 A 类份额，否则取第一个
            a = next((x for x in subs if 'A' in str(x.get('SHARE_CLASS') or '')), subs[0])
            sub = a.get('PROD_CODE') or code
    res['sub_code'] = sub
    p = api('/bylc-api/product/perform', PROD_CODE=sub)
    dd = p.get('data') or {}
    if isinstance(dd, dict):
        for k in res:
            if k != 'sub_code':
                res[k] = dd.get(k)
    return res


def parse_bench(s):
    """只接受纯数字百分比：'2.10%-2.60%' / '1.90%'。公式挂钩型返回 None。"""
    if not s:
        return None
    s = str(s).strip()
    if re.search(r'[\u4e00-\u9fff]|指数|中债|x|\+', s, re.I):
        return None
    m = re.fullmatch(r'([\d.]+)\s*%\s*[-~至]\s*([\d.]+)\s*%', s)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 0 <= a <= 10 and 0 <= b <= 10 and a <= b:
            return (a, b)
        return None
    m = re.fullmatch(r'([\d.]+)\s*%', s)
    if m:
        a = float(m.group(1))
        return (a, a) if 0 <= a <= 10 else None
    return None


def fmt_date(s):
    s = str(s or '').strip()
    return f'{s[:4]}-{s[4:6]}-{s[6:8]}' if re.fullmatch(r'\d{8}', s) else None


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def build(it, idx, ex):
    code = it.get('PROD_CODE') or ''
    risk = RISK_MAP.get(str(it.get('RISK_LEVEL')), 'R3')
    st_code, st_name = STATUS_MAP.get(str(it.get('PROD_STATUS')), (None, None))
    bench = parse_bench(it.get('PERFORMANCE_BENCHMARK'))
    inc = to_float(ex.get('INC'))
    nav = to_float(ex.get('NAV'))
    nav_dt = str(ex.get('NAV_DATE') or '') if ex.get('NAV_DATE') else None

    perf = perf_type = perf_dt = None
    perf_mid = None
    if bench:
        a, b = bench
        perf = f'{a}%~{b}%' if a != b else f'{a}%'
        perf_type = '业绩比较基准'
        perf_mid = round((a + b) / 2, 3)
        perf_dt = f'{nav_dt[4:6]}/{nav_dt[6:8]}' if nav_dt and len(nav_dt) >= 8 else ''
    elif inc is not None and 0 < inc <= 15:
        perf = f'{inc}%'
        perf_type = '成立以来年化'
        perf_mid = inc
        perf_dt = f'{nav_dt[4:6]}/{nav_dt[6:8]}' if nav_dt and len(nav_dt) >= 8 else ''

    # 近1月：官方 MONTHINC 为年化，按实际区间天数反推为区间涨幅
    ret_1m = None
    m = to_float(ex.get('MONTHINC'))
    if m is not None and ex.get('MONTHINC_START_DATE') and nav_dt:
        try:
            d1 = datetime.datetime.strptime(str(ex['MONTHINC_START_DATE']), '%Y%m%d')
            d2 = datetime.datetime.strptime(nav_dt, '%Y%m%d')
            days = (d2 - d1).days
            if not (20 <= days <= 40):
                days = 30
            ret_1m = round(m * days / 365.0, 2)
        except Exception:
            pass

    est = fmt_date(it.get('ESTABLISH_DATE'))
    age_years = None
    if est:
        try:
            age_years = round((datetime.date.today() - datetime.date.fromisoformat(est)).days / 365.25, 2)
        except Exception:
            pass

    term_days = to_float(it.get('PROD_TERM_DAYS'))
    min_amt = to_float(it.get('INIT_PURCHASE'))
    return {
        'id': idx,
        'name': (it.get('PROD_NAME') or '').strip(),
        'risk': risk,
        'type': '理财',
        'issuer': (it.get('MANAGER_NAME') or '北银理财有限责任公司').strip(),
        'src': 'live',                       # 关键：避免被 hideOffshelf 过滤
        'status_code': st_code,
        'status': st_name,
        'public_flag': '公募',
        'detail_url': DETAIL + code,
        'perf': perf,
        'perf_type': perf_type,
        'perf_dt': perf_dt,
        'perf_mid': perf_mid,
        'nav': nav,
        'nav_dt': nav_dt,
        'yield_min': bench[0] if bench else None,
        'yield_max': bench[1] if bench else None,
        'yield_mid': perf_mid,
        'yield_source': 'bob_api' if perf_mid is not None else None,
        'yield_date': fmt_date(nav_dt) if nav_dt else None,
        'ret_1m': ret_1m,
        'ret_1m_est': False,
        'term_days': int(term_days) if term_days is not None else None,
        'term_label': (it.get('PROD_TERM_DESC') or it.get('OPEN_TYPE_DESC') or '').strip() or None,
        'min_amount': min_amt,
        'start_date': fmt_date(it.get('IPO_START_DATE')),
        'end_date': fmt_date(it.get('END_DATE')),
        'open_date': None,
        'age_years': age_years,
        'guaranteed': False,
        'private': False,
        'est_drawdown': DD_MAP.get(risk, 1.0),
        'sales_target': None,
        'note': '北银理财官网产品公示；收益/净值取首个子份额（通常A类），近1月由官方年化业绩反推。',
        'prod_code': code,
        'share_code': ex.get('sub_code'),
        'prod_status': it.get('PROD_STATUS'),
    }


def main():
    t0 = time.time()
    items = fetch_all()
    print(f'products = {len(items)}', flush=True)
    with ThreadPoolExecutor(max_workers=12) as pool:
        extras = list(pool.map(enrich, items))
    products = [build(it, i + 1, ex) for i, (it, ex) in enumerate(zip(items, extras))
                if str(it.get('PROD_STATUS')) != '04']  # 剔除已到期
    print('kept =', len(products), flush=True)
    def cnt(k):
        return sum(1 for p in products if p.get(k) is not None)
    for k in ['perf', 'perf_mid', 'nav', 'ret_1m', 'yield_mid', 'min_amount', 'term_days']:
        print(f'  {k}: {cnt(k)}', flush=True)

    meta = {
        'source': '北银理财官网产品公示（免登录接口 search/subs/perform）',
        'data_date': TODAY, 'live_date': TODAY, 'fetched_at': TODAY,
        'count': len(products), 'bank': '北京银行',
    }
    data = {'meta': meta, 'products': products}
    with open(os.path.join(D, 'bob.js'), 'w', encoding='utf-8') as f:
        f.write('window.BOB_DATA = ')
        json.dump(data, f, ensure_ascii=False)
        f.write(';\n')
    with open(os.path.join(D, 'bob_raw.json'), 'w', encoding='utf-8') as f:
        json.dump({'fetched_at': TODAY, 'items': items, 'extras': extras}, f, ensure_ascii=False)
    print('bob.js bytes =', os.path.getsize(os.path.join(D, 'bob.js')), flush=True)
    print('elapsed %.1fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
