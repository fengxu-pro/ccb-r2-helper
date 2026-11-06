# -*- coding: utf-8 -*-
"""把 fetch_cmb.py 抓到的 cmb_raw.json 清洗成 cmb.js（window.CMB_DATA）。

过滤：只保留公募(pubPrv=A)、风险 R1~R4（排除 R5 高风险）。
收益口径：zbasPrf 仅接受纯数字百分比；公式挂钩型（活期利率/中债指数/分档）标「挂钩型」，
不取描述里的数字冒充。
近1月收益：取官方 pastPerf 的 A 档 znavYld（区间实际涨幅）。
  口径验证：A/B/C/D/E 档「区间涨幅÷年化×365」中位分别为 34/94/186/369/1098 天，
  即近1月/近3月/近6月/近1年/近3年；100137 的 A=+0.12% 与官网累计净值近1月涨幅吻合。
"""
import json, re, os, sys, ast, datetime

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

D = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()
DD_MAP = {'R1': 0.1, 'R2': 0.5, 'R3': 1.5, 'R4': 3.0, 'R5': 5.0}
DETAIL = ('https://www.cmbchina.com/cfweb/Personal/saproductdetail.aspx'
          '?saaCod={saa}&funCod={code}&type=prodvalue')


def parse_rate(s):
    if not s:
        return None
    s = str(s).strip()
    if re.search(r'[\u4e00-\u9fff]|指数|中债|利率|×|\+', s, re.I):
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


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def cn_date(s):
    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', str(s or ''))
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else None


def strip_none(d):
    return {k: v for k, v in d.items() if v is not None}


def past_perf_1m(it):
    """官方过往业绩 A 档 = 近1月区间实际收益率(%，累计净值口径)。"""
    s = it.get('pastPerf')
    d = s if isinstance(s, dict) else None
    if d is None and isinstance(s, str) and s.strip():
        try:
            d = ast.literal_eval(s)
        except Exception:
            return None
    for e in ((d or {}).get('tqilstw4z3') or []):
        if str(e.get('zprfTyp')) == 'A':
            v = to_float(e.get('znavYld'))
            if v is not None and -10 <= v <= 10:
                return round(v, 2)
    return None


def build(it, idx):
    code = str(it.get('code') or '')
    risk = str(it.get('risk') or 'R3').upper()
    rate = parse_rate(it.get('zbasPrf'))
    formula = bool(it.get('zbasPrf')) and rate is None
    perf = perf_mid = None
    perf_type = None
    if rate:
        a, b = rate
        perf = f'{a}%~{b}%' if a != b else f'{a}%'
        perf_mid = round((a + b) / 2, 3)
        perf_type = '业绩比较基准'
    elif formula:
        perf = '挂钩型'
        perf_type = '业绩比较基准'

    nav = to_float(it.get('dnvval'))
    est = cn_date(it.get('zrunDat'))
    age_years = None
    if est:
        try:
            age_years = round((datetime.date.today() - datetime.date.fromisoformat(est)).days / 365.25, 2)
        except Exception:
            pass
    saa = str(it.get('saacod') or '')
    return strip_none({
        'id': idx,
        'name': (it.get('name') or it.get('shortName') or '').strip(),
        'risk': risk,
        'type': '理财',
        'issuer': (it.get('zcrpNam') or it.get('orgName') or '').strip() or '招银理财',
        'src': 'live',
        'status_code': None,          # 官网 prdsts 仅 1/2，语义不明确，不臆造在售状态
        'status': None,
        'public_flag': '公募',
        'detail_url': DETAIL.format(saa=saa, code=code),
        'perf': perf,
        'perf_type': perf_type,
        'perf_dt': '',
        'perf_mid': perf_mid,
        'nav': nav,
        'nav_dt': None,
        'yield_min': rate[0] if rate else None,
        'yield_max': rate[1] if rate else None,
        'yield_mid': perf_mid,
        'yield_source': 'cmb_api' if perf_mid is not None else None,
        'yield_date': None,
        'ret_1m': past_perf_1m(it),
        'ret_1m_est': False,
        'term_days': None,
        'term_label': None,
        'min_amount': to_float(it.get('buynfq')),
        'start_date': est,
        'end_date': None,
        'open_date': None,
        'age_years': age_years,
        'guaranteed': False,
        'private': False,
        'est_drawdown': DD_MAP.get(risk, 1.0),
        'sales_target': None,
        'note': '招商银行理财产品统一查询平台（代销，含多家理财子公司）；公式挂钩型基准不显示数值；近1月收益取官方过往业绩A档（累计净值口径）。',
        'prod_code': code,
        'prod_status': it.get('prdsts'),
    })


def main():
    raw = json.load(open(os.path.join(D, 'cmb_raw.json'), encoding='utf-8'))
    items = raw['items']
    kept = [x for x in items
            if str(x.get('pubPrv')) == 'A' and str(x.get('risk')).upper() in ('R1', 'R2', 'R3', 'R4')]
    print('raw =', len(items), ' kept =', len(kept), flush=True)
    products = [build(x, i + 1) for i, x in enumerate(kept)]
    for k in ['perf', 'perf_mid', 'nav', 'min_amount', 'ret_1m']:
        print(f'  {k}: {sum(1 for p in products if p.get(k) is not None)}', flush=True)
    meta = {'source': '招商银行理财产品统一查询平台（免登录，浏览器签名重放）',
            'data_date': TODAY, 'live_date': TODAY, 'fetched_at': TODAY,
            'count': len(products), 'bank': '招商银行'}
    with open(os.path.join(D, 'cmb.js'), 'w', encoding='utf-8') as f:
        f.write('window.CMB_DATA = ')
        json.dump({'meta': meta, 'products': products}, f, ensure_ascii=False)
        f.write(';\n')
    print('cmb.js bytes =', os.path.getsize(os.path.join(D, 'cmb.js')), flush=True)


if __name__ == '__main__':
    main()
