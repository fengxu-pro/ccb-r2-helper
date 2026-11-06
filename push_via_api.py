# -*- coding: utf-8 -*-
"""git over HTTPS 被网络重置时的备用发布通道：用 GitHub Git Data API 一次性创建 commit。

等价于 git push：为变更文件创建 blob -> 基于远端 tree 建新 tree -> 建 commit -> 更新 refs/heads/main。
用法: python push_via_api.py [base_sha]
"""
import os, re, sys, json, base64, subprocess, urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

D = os.path.dirname(os.path.abspath(__file__))
# token 只从本机 git remote URL 读取，绝不写进脚本/仓库
_remote = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=D).decode().strip()
_m = re.search(r'https://([^@]+)@github\.com', _remote)
if not _m:
    raise SystemExit('remote.origin.url 中未找到 token')
TOKEN = _m.group(1)
REPO = 'fengxu-pro/ccb-r2-helper'
API = 'https://api.github.com/repos/' + REPO
HDRS = {'Authorization': 'token ' + TOKEN, 'User-Agent': 'ccb-r2-helper-publisher',
        'Content-Type': 'application/json', 'Accept': 'application/vnd.github+json'}


def req(path, method='GET', payload=None, timeout=180):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(API + path, data=data, headers=HDRS, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def git(*args):
    return subprocess.check_output(['git'] + list(args), cwd=D).decode('utf-8').strip()


# 需要同步到 Pages 的文件（本地/远端历史分叉时不能用 git diff 远端 SHA 当基准）
FILES = [
    'index.html', 'sw.js', 'version.json', 'manifest.webmanifest',
    'data.js', 'bob.js', 'cmb.js', 'bcm.js', 'live.json', '.gitignore',
    'daily_update.py', 'fetch_bob.py', 'fetch_cmb.py', 'build_cmb.py',
    'fetch_bcm.py', 'push_via_api.py',
]


def main():
    base = req('/git/refs/heads/main')['object']['sha']   # 远端 parent / tree 基准
    msg = git('log', '-1', '--pretty=%B')
    files = [f for f in FILES if os.path.exists(os.path.join(D, f))]
    print('remote base =', base[:8], 'files =', len(files), flush=True)
    base_commit = req('/git/commits/' + base)
    base_tree = base_commit['tree']['sha']

    tree = []
    for f in files:
        p = os.path.join(D, f)
        if not os.path.exists(p):
            tree.append({'path': f, 'mode': '100644', 'type': 'blob', 'sha': None})
            print('  delete', f, flush=True)
            continue
        raw = open(p, 'rb').read()
        blob = req('/git/blobs', 'POST',
                   {'content': base64.b64encode(raw).decode(), 'encoding': 'base64'})
        tree.append({'path': f, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
        print('  blob', f, len(raw), 'bytes ->', blob['sha'][:8], flush=True)

    new_tree = req('/git/trees', 'POST', {'base_tree': base_tree, 'tree': tree})['sha']
    new_commit = req('/git/commits', 'POST',
                     {'message': msg, 'tree': new_tree, 'parents': [base]})['sha']
    print('new commit =', new_commit[:8], flush=True)
    ref = req('/git/refs/heads/main', 'PATCH', {'sha': new_commit, 'force': False})
    print('ref ->', ref['object']['sha'][:8], flush=True)
    # 本地 ref 同步到 API 创建的 commit（内容一致，工作区不变，避免本地/远端分叉）
    try:
        git('update-ref', 'refs/remotes/origin/main', new_commit)
        git('update-ref', 'refs/heads/main', new_commit)
    except Exception as e:
        print('local ref update skipped:', e, flush=True)
    print('PUBLISH_OK', flush=True)


if __name__ == '__main__':
    main()
