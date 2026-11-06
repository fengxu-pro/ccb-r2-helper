# -*- coding: utf-8 -*-
"""招行理财产品统一查询平台（finprod.paas.cmbchina.com）抓取。

该站 /api/prod/queryProdList 有国密 SM4-ECB 签名（前端 CryptoJS 定制实现，直接复现成本高），
因此用 CDP 启动本机 Edge，注入 fetch hook 捕获页面自己生成的签名请求头，
再在页面上下文里用同一组头批量重放分页请求，拿全量 JSON。

输出：cmb_raw.json（原始），供 build 脚本清洗成 cmb.js。
"""
import os, sys, json, time, subprocess, urllib.request
import websocket

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9237
PROFILE = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'), 'cmb-cdp-profile')
URL = 'https://finprod.paas.cmbchina.com/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cmb_raw.json')

HOOK = r"""
(function(){
  var of = window.fetch;
  window.fetch = function(input, init){
    try{
      var u = (typeof input === 'string') ? input : (input && input.url);
      if(u && String(u).indexOf('/prod/queryProdList') >= 0 && init && init.headers && !window.__CMB_HDR__){
        var h = {}, hs = init.headers;
        if(hs && typeof hs.forEach === 'function'){ hs.forEach(function(v,k){ h[k]=v; }); }
        else { Object.assign(h, hs || {}); }
        window.__CMB_HDR__ = h;
        window.__CMB_URL__ = u;
        window.__CMB_BODY__ = init.body;
      }
    }catch(e){}
    return of.apply(this, arguments);
  };
})();
"""

REPLAY = r"""
(function(){
  window.__CMB_DONE__ = false;
  window.__CMB_PROGRESS__ = 'start';
  (async function(){
    var H = window.__CMB_HDR__;
    if(!H){ window.__CMB_RESULT__ = JSON.stringify({error:'no signed headers'}); window.__CMB_DONE__=true; return; }
    var tpl;
    try{ tpl = JSON.parse(window.__CMB_BODY__); }catch(e){ tpl = null; }
    var out = [], total = null, firstErr = null, p = 1, stop = false;
    function onePage(pg){
      var body = tpl ? JSON.parse(JSON.stringify(tpl)) :
        {keyWords:'',type:'',isOwn:'',isPublic:'',status:'',pageNO:pg,pageSize:50,crossFinance:'',riskLevel:'',obligate:''};
      body.pageNO = pg;
      var ctrl = new AbortController();
      var timer = setTimeout(function(){ ctrl.abort(); }, 15000);
      return fetch('/api/prod/queryProdList', {method:'POST', headers:H, body:JSON.stringify(body), signal:ctrl.signal})
        .then(function(r){ return r.json(); })
        .then(function(j){ clearTimeout(timer); return {pg:pg, j:j}; })
        .catch(function(e){ clearTimeout(timer); return {pg:pg, err:String(e)}; });
    }
    while(p <= 260 && !stop){
      var batch = [];
      for(var i=0; i<6 && p<=260; i++, p++) batch.push(p);
      var rs = await Promise.all(batch.map(onePage));
      rs.sort(function(a,b){ return a.pg-b.pg; });
      for(var k=0;k<rs.length;k++){
        var it = rs[k];
        if(it.err){ if(!firstErr) firstErr='fetch: '+it.err; continue; }
        var j = it.j;
        if(j.code !== 'SUC0000'){
          if(!firstErr) firstErr = j.code+' '+j.message;
          if(it.pg === 1){ stop=true; break; }
          continue;
        }
        var list = (j.data && j.data.list) || [];
        if(total === null) total = j.data && j.data.totalSize;
        out.push.apply(out, list);
        if(!list.length) stop = true;
      }
      window.__CMB_PROGRESS__ = 'through page '+(p-1)+' rows '+out.length+' total '+total;
      window.__CMB_PARTIAL__ = JSON.stringify({total:total, rows:out.length, err:firstErr, data:out});
      if(total && out.length >= total) stop = true;
      if(firstErr && out.length === 0) stop = true;
    }
    window.__CMB_RESULT__ = window.__CMB_PARTIAL__ || JSON.stringify({total:total, rows:0, err:firstErr, data:[]});
    window.__CMB_DONE__ = true;
  })();
  return 'started';
})()
"""


def main():
    proc = subprocess.Popen(
        [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--disable-extensions',
         '--remote-debugging-port=%d' % PORT, '--user-data-dir=' + PROFILE, 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        # 等调试端口起来
        tgt = None
        for _ in range(40):
            try:
                tabs = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % PORT, timeout=2))
                tgt = next((t for t in tabs if t.get('type') == 'page'), None)
                if tgt:
                    break
            except Exception:
                time.sleep(0.5)
        if not tgt:
            raise RuntimeError('CDP 端口未就绪')
        ws = websocket.create_connection(tgt['webSocketDebuggerUrl'], timeout=30)
        seq = [0]

        def cmd(method, params=None):
            seq[0] += 1
            mid = seq[0]
            ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get('id') == mid:
                    return msg

        cmd('Page.enable')
        cmd('Runtime.enable')
        cmd('Page.addScriptToEvaluateOnNewDocument', {'source': HOOK})
        cmd('Page.navigate', {'url': URL})
        # 等页面自己发出带签名的请求
        hdr_ok = False
        for _ in range(40):
            time.sleep(0.5)
            r = cmd('Runtime.evaluate', {'expression': '!!window.__CMB_HDR__', 'returnByValue': True})
            if (r.get('result') or {}).get('result', {}).get('value'):
                hdr_ok = True
                break
        print('signed headers captured =', hdr_ok, flush=True)
        if not hdr_ok:
            raise RuntimeError('未捕获到签名请求头')

        cmd('Runtime.evaluate', {'expression': REPLAY, 'returnByValue': True})
        # 后台执行，轮询完成标记（避免单条 CDP 命令长时间阻塞）
        raw = None
        for i in range(600):   # 最多 5 分钟
            time.sleep(0.5)
            r = cmd('Runtime.evaluate', {'expression': 'window.__CMB_DONE__ ? window.__CMB_RESULT__ : null', 'returnByValue': True})
            raw = (r.get('result') or {}).get('result', {}).get('value')
            if raw:
                break
            if i % 20 == 19:
                pr = cmd('Runtime.evaluate', {'expression': 'window.__CMB_PROGRESS__', 'returnByValue': True})
                print('  progress:', (pr.get('result') or {}).get('result', {}).get('value'), flush=True)
        if not raw:
            # 超时兜底：保存已抓到的部分
            r = cmd('Runtime.evaluate', {'expression': 'window.__CMB_PARTIAL__ || "{}"', 'returnByValue': True})
            raw = (r.get('result') or {}).get('result', {}).get('value') or '{}'
            print('WARN: 未跑完，保存部分数据', flush=True)
        payload = json.loads(raw)
        if payload.get('error'):
            raise RuntimeError('API: ' + str(payload['error']))
        print('total =', payload.get('total'), ' rows =', payload.get('rows'), flush=True)
        data = payload['data']
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump({'fetched_at': time.strftime('%Y-%m-%d'), 'total': payload.get('total'),
                       'items': data}, f, ensure_ascii=False)
        print('cmb_raw.json bytes =', os.path.getsize(OUT), flush=True)
        if data:
            print('item keys:', list(data[0].keys())[:40], flush=True)
    finally:
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == '__main__':
    main()
