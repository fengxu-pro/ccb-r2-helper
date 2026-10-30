# 建行 R1/R2 优选助手（安卓 PWA App）

基于建设银行官网《在售代理类产品信息公示》+ 官网实时接口（NISP00）构建的安卓端理财产品筛选与推荐工具。默认仅展示 **R1/R2** 优质产品，支持多维组合筛选与一键推荐 5 / 10 / 20 / 50 只。

## 在线访问 / OTA 地址（已部署）

- **正式地址（GitHub Pages）**：<https://fengxu-pro.github.io/ccb-r2-helper/>
- 手机浏览器打开该地址 → 菜单 → **「添加到主屏幕」** 即装即用（PWA，离线可用）。
- App 内右上角「**更新**」按钮会实时拉取该地址下的 `version.json`，版本号更高时自动跳转新版页面（OTA）。
- 发布新版流程：本地改代码 → `git push` 到本仓库 `main` 分支 → Pages 自动重新发布（约 1 分钟）→ 用户端点「更新」即拉到新版。

## 文件清单

| 文件 | 作用 |
|---|---|
| `index.html` | 应用本体（界面 + 筛选/**排序栏**/评分/推荐 + 实时状态徽章 + 实时收益指标 + 未来页 + 拉新 + OTA） |
| `data.js` | 内置数据快照：**2026-10-28 实时接口快照（3532 只，含 3238 只实时在售 + 294 只公示明细）**；其中 **613 只在售代销理财带实时收益指标**（2026-10-30 自建行财富频道 NLCQ11 接口抓取：现金管理类=七日年化收益率、开放式=成立以来年化收益率、均带数据区间与最新净值；封闭式=最新业绩比较基准）；另约 1000 只 R1/R2 的**业绩比较基准**由 2026-10-29 从官方 PDF 详情页抓取（带 `官方基准 · 2026-10-29` 标签） |
| `libs/xlsx.full.min.js` | SheetJS（浏览器端解析公示 Excel，供「拉新/导入」用） |
| `manifest.webmanifest` | PWA 清单（安装到主屏幕的图标/名称/全屏配置） |
| `sw.js` | Service Worker（离线缓存 + 版本自动更新 = OTA 基础） |
| `version.json` | OTA 版本清单（「更新」按钮比对用） |
| `icon-192.png / icon-512.png` | 应用图标 |

## 数据来源与时效（重要）

- **主数据源 = 建行官网实时接口（NISP00）**：接口公开、无需登录、无 Referer 校验，覆盖理财/基金/结构性存款在售全量。已内置 **2026-10-28** 的服务器拉取快照（3532 只）。
- **辅助数据源① = 官方 PDF 详情附件**：NISP00 返回的 `URL_Vld_Inf` 中约半数（1860+ 只）是**公开 PDF**（免登录、HTTP 200），里面直接印着当期「业绩比较基准」。已用服务端 `pypdf` 批量抓取 **R1/R2 共 1000+ 只有 PDF 的产品**，提取真实基准写回数据（卡片标注「官方基准 · 2026-10-29」）。这是 App 里收益率数字的真实来源。
- **辅助数据源② = 官网《在售代理类产品信息公示》Excel**：含完整收益率/期限/起存金额，但更新滞后（内置 2026-04-15 期，共 294 只，其中 83 只与实时清单按名称匹配）。仅作为旧数据的灰色「数据2026-04-15」标签保留，供参考。
- 实时清单自带**产品状态**（申购中/认购中/可预约/预售）与**官方详情页直链**。**收益率**以官方 PDF 提取为主、旧公示为辅；挂钩型产品无固定基准（标注「基准随市场浮动」）；其余净值型无基准的显示「—」并附官方详情页链接，不臆造数据。
- **详情页 JSONP 接口被建行反爬拦截**（需登录态/Referer/同站 Cookie），无法程序化抓取；但**详情页 PDF 附件不受此限制**，可直接抓取（见上）。

## 如何在安卓手机上使用

### 方式 A（零门槛）：直接下载安装 APK（推荐）
1. 手机浏览器打开 APK 直链下载：**<https://fengxu-pro.github.io/ccb-r2-helper/ccb-r2-helper-v1.0.0.apk>**
2. 下载完成后点开安装包；系统提示「未知来源应用」时，选择**允许/仍要安装**（各品牌路径：设置 → 安全 → 安装未知应用）。
3. 桌面出现「**建行优选**」独立图标，点开即全屏运行。App 内容与官网版完全同源：
   - 数据/页面全部来自 GitHub Pages（HTTPS），**Service Worker 离线缓存与 OTA 自动更新在 App 内照常生效**；
   - 右上角「更新」按钮、底部「拉新」等一切功能不变；
   - 升级 App 内容无需重装 APK——在 Pages 发布新版后，App 内点「更新」即可。
4. App 外部链接（建行官方详情页等）会自动交给系统浏览器打开。

### 方式 B（备选）：不装 APK，直接「添加到主屏幕」
1. 安卓 Chrome 打开 <https://fengxu-pro.github.io/ccb-r2-helper/> → 菜单 → **「添加到主屏幕 / 安装应用」**。
2. 体验与 APK 基本一致（PWA，离线可用）。

### 方式 C：重新打包 / 更新 APK（本机工具链）
本机已具备完整工具链（无需下载）：
- JDK 17：`C:\Users\fengxu\.workbuddy\binaries\android\jdk17\jdk-17.0.20.1+1`
- Android SDK：`C:\Users\fengxu\.workbuddy\binaries\android\sdk`（platforms/android-35 + build-tools/35.0.0）

构建流程（aapt2 → javac → d8 → zip → zipalign → apksigner）：

```bash
cd apk
aapt2 compile --dir res -o flat.zip
aapt2 link -o base.apk -I <sdk>/platforms/android-35/android.jar \
  --manifest AndroidManifest.xml -R flat.zip --java gen --auto-add-overlay
javac -encoding UTF-8 -source 8 -target 8 -cp <sdk>/platforms/android-35/android.jar \
  -d classes gen/com/fengxu/ccbhelper/R.java java/com/fengxu/ccbhelper/MainActivity.java
d8 --release --lib <sdk>/platforms/android-35/android.jar --output dexout classes/com/fengxu/ccbhelper/*.class
# 把 classes.dex 注入 base.apk（python zipfile），再：
zipalign -f 4 base_dex.apk aligned.apk
apksigner sign --ks ccb-helper.keystore --ks-key-alias ccbhelper \
  --ks-pass pass:ccbhelper2026 --key-pass pass:ccbhelper2026 \
  --out ../ccb-r2-helper-v1.0.0.apk aligned.apk
```

> ⚠️ 签名密钥：`apk/ccb-helper.keystore`（口令 ccbhelper2026，别名 ccbhelper，证书 SHA-256
> `a4ad1709834cf71a164350885b4d100b9a19237f85f9a5d9f01116d5977cbd82`）。
> **请备份好该文件**——升级安装包必须用同一密钥签名，否则手机上无法覆盖安装。
> 该密钥未提交到仓库（已 gitignore），仅保存在本机。

### 方式 D：局域网快速试用
电脑上 `python -m http.server 8000`，手机连同一 WiFi 访问 `http://电脑IP:8000`（仅测试，http 下 PWA 安装/OTA 不可用）。

## 实时拉新（在 App 内「拉新」）

App 内「拉新」针对**实时接口**做了三档尝试，**无需登录**：

1. **① 直接请求实时接口**（首选）：用浏览器可配置的代理地址转发 `https://www2.ccb.com/tran/WCCMainPlatV5?...&TXCODE=NISP00` 请求，解析返回的 `PD_Lst_Itm` 全量在售清单，实时刷新状态徽章与「未来」页，并**持久化到本机 localStorage**（下次打开自动还原）。
2. **② 代理拉取公示 Excel**（备选）：含完整收益率/期限/起存，但更新滞后。粘贴最新链接或导入本地文件。
3. **③ 导入本地 Excel 文件**：代理失败时的兜底——从建行官网/APP 下载最新 Excel，直接导入解析。

> ⚠️ 公共 CORS 代理（allorigins / corsproxy.io / codetabs）目前对建行域名均不稳定或不可用。最稳方案是自己部署一个 Cloudflare Worker 代理（见下），把其地址粘贴到「拉新」面板的代理输入框即可。
>
> 不论是否拉新，内置的 **2026-10-28 实时快照**始终可用，App 开箱即见全量在售产品。

### 自部署 Cloudflare Worker 代理（推荐）

在 Cloudflare 新建 Worker，粘贴以下代码并部署，把 `https://<你的子域>.workers.dev/?url=<目标URL>` 填进 App 拉新的代理框：

```js
export default {
  async fetch(req){
    const u = new URL(req.url).searchParams.get('url');
    if(!u) return new Response('missing url', {status:400});
    const r = await fetch(u, {
      headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www2.ccb.com/' }
    });
    const t = await r.text();
    return new Response(t, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': r.headers.get('Content-Type') || 'application/json'
      }
    });
  }
}
```

### 进阶：让「拉新」也能实时刷新收益率

上面的 Worker 只转发文本（用于拉在售清单）。若想让 App 按钮**实时抓取某只产品的真实收益率**，把 Worker 升级为支持 `?pdf=<PDF链接>`：Worker 拉取 PDF 后把内容（或经边缘函数解析后的基准 JSON）回传，前端用 `pdf.js` 提取「业绩比较基准」即可。

> 说明：默认内置的**批量烘焙快照**已覆盖 1000+ 只 R1/R2 的真实基准（卡片标注「官方基准 · 2026-10-29」），绝大多数有固定基准的产品都已补全；浏览器端 pdf.js 解析中文嵌入字体 PDF 准确率约 90%+，偶有误判，可与内置基准互为校验。除非你频繁需要「点一下就拿到今天最新基准」，否则内置快照已足够。

## OTA 升级

- **应用层**：部署到 https 后，覆盖上传新版本文件即可自动更新（SW skipWaiting + 网络优先策略）。
- **数据层**：App 内「拉新」按钮即数据 OTA，可实时拉取最新在售清单并重新推荐（自动本地持久化）。
- `version.json` 中改 `version` 字段（如 1.1.0 → 1.1.1），App 内「更新」按钮会检测并提示刷新。

## 筛选条件（可自由组合，默认 R1/R2）

风险等级(R0-R4，默认 R1/R2)、产品类型(理财/基金)、业绩比较基准区间、是否含净值型(无基准)、预估最大回撤上限、产品期限(开放式/封闭式天数)、起存金额上限(1元/1万/5万/30万)、发行机构(多选)、保本型、排除私行专享、发行年限、关键词搜索。
排序：综合评分 / 收益率 / 期限 / 起存 / 回撤。一键推荐 **5 / 10 / 20 / 50** 只（按综合评分取 Top N）。

推荐分 = 收益性 35% + 安全性(低回撤) 30% + 流动性 20% + 低门槛 10% + 机构(建信理财加权) 5%。

## 底部「未来」页

- **待发售 / 认购中**：含公示中尚未开始或正在认购的产品，以及实时状态为「认购中/可预约/预售」的在售新品。
- **封闭待开放**：当前已封闭、但按「募集终止日 + 产品期限」推算有明确未来开放日的优质产品。
- 页内可单独筛选 R1/R2、可排除私行专享。

## 数据局限（如实说明）

- **收益率真实来源 = 官方 PDF 详情页**（2026-10-29 服务端批量抓取约 1000+ 只 R1/R2），卡片标注绿色「官方基准 · 2026-10-29」；挂钩型产品无固定数字（标注「基准随市场浮动」）；少数无 PDF / PDF 为公式型 / 抓取失败的仍显示「—」并附官方链接。旧公示 Excel（2026-04-15）仅作灰色历史参考标签。
- 官方公示**不含历史回撤与成立日期**：回撤为按风险等级的预估代理值（非官方）；发行年限仅封闭式可按募集起始日估算。
- 银行理财已全面净值化、**不保本**（仅 4 只 R0 结构性存款保本）。本工具仅为研究辅助，**不构成投资建议**。
