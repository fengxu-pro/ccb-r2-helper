# -*- coding: utf-8 -*-
"""每日自动更新流水线：抓建行实时在售+收益指标+近1月 -> 重建 data.js -> 更新 version.json -> 推送 GitHub Pages。

用法: python daily_update.py [--no-push]
步骤失败会重试；整体失败时以非 0 退出，便于自动化任务感知。
"""
import subprocess, sys, os, json, time, datetime

D = os.path.dirname(os.path.abspath(__file__))
os.chdir(D)
TODAY = datetime.date.today().isoformat()

def run(cmd, desc, retries=3, timeout=3600):
    for i in range(1, retries + 1):
        print(f"[{desc}] try {i}: {' '.join(cmd)}", flush=True)
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = (r.stdout or b'').decode('utf-8', errors='ignore')
        err = (r.stderr or b'').decode('utf-8', errors='ignore')
        tail = (out + err).strip().splitlines()
        for ln in tail[-3:]:
            print("   |", ln, flush=True)
        if r.returncode == 0:
            print(f"[{desc}] OK", flush=True)
            return True
        time.sleep(5 * i)
    print(f"[{desc}] FAILED after {retries} tries", flush=True)
    return False

PY = sys.executable
ok = True

# 1. 实时在售清单(NISP00) -> 与 Excel 快照合并 -> 重建 data.js
ok &= run([PY, 'fetch_live.py'], 'live')
# 2. 收益指标(NLCQ11) -> wealth_perf.json -> 合并
ok &= run([PY, 'fetch_perf.py'], 'perf')
ok &= run([PY, 'merge_perf.py'], 'merge-perf', retries=2)
# 3. 近1月收益(NLCZST) -> wealth_1m.json -> 合并
ok &= run([PY, 'fetch_1m.py'], '1m')
ok &= run([PY, 'merge_1m.py'], 'merge-1m', retries=2)

if not ok:
    print('PIPELINE FAILED', flush=True)
    sys.exit(1)

# 3b. 其余三家银行：失败仅告警，不阻断建行数据发布（保留上次快照）
if not run([PY, 'fetch_bob.py'], 'bob', retries=2):
    print('WARN: 北京银行抓取失败，保留上次 bob.js', flush=True)
# 招行：CDP 启动本机 Edge 捕获页面签名后重放分页（约 2 分钟），再清洗成 cmb.js
if run([PY, 'fetch_cmb.py'], 'cmb-fetch', retries=1):
    run([PY, 'build_cmb.py'], 'cmb-build', retries=1)
else:
    print('WARN: 招商银行抓取失败，保留上次 cmb.js', flush=True)
if not run([PY, 'fetch_bcm.py'], 'bcm', retries=2):
    print('WARN: 交通银行抓取失败，保留上次 bcm.js', flush=True)

# 4. 更新 version.json 日期
vd = json.load(open('version.json', encoding='utf-8'))
vd['live_date'] = TODAY
vd['perf_date'] = TODAY
vd['ret_1m_date'] = TODAY
vd['bob_date'] = TODAY
vd['cmb_date'] = TODAY
vd['bcm_date'] = TODAY
vd['notes'] = f'自动快照 {TODAY}：建设/北京/招商/交通四家银行数据已刷新。'
json.dump(vd, open('version.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('version.json ->', vd['version'], TODAY, flush=True)

# 4b. 导出同源 live.json：App「拉新」直接从 Pages 同源拉取，零 CORS 零代理
try:
    lp = json.load(open('live_products.json', encoding='utf-8'))
    json.dump({'date': TODAY, 'count': len(lp), 'items': lp},
              open('live.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print('live.json bytes =', os.path.getsize('live.json'), flush=True)
except Exception as e:
    print('live.json export FAILED:', e, flush=True)

if '--no-push' in sys.argv:
    print('DONE (no push)', flush=True)
    sys.exit(0)

# 5. 提交并推送（网络波动多试几次）
run(['git', 'add', 'data.js', 'bob.js', 'cmb.js', 'bcm.js', 'version.json', 'live.json', 'index.html', 'sw.js',
     'products.json', 'live_products.json',
     'wealth_perf.json', 'wealth_1m.json', 'nisp00.json'], 'git-add', retries=1, timeout=300)
msg = f"auto snapshot {TODAY}"
subprocess.run(['git', 'commit', '-m', msg], capture_output=True)
for i in range(1, 9):
    r = subprocess.run(['git', 'push', 'origin', 'HEAD'], capture_output=True, timeout=180)
    tail = ((r.stdout or b'') + (r.stderr or b'')).decode('utf-8', errors='ignore').strip().splitlines()
    for ln in tail[-2:]:
        print("   |", ln, flush=True)
    if r.returncode == 0:
        print('PUSH OK', flush=True)
        break
    time.sleep(10 * i)
else:
    print('PUSH FAILED - 数据已在本地更新，可稍后手动 git push', flush=True)
    sys.exit(2)
print('DONE', flush=True)
