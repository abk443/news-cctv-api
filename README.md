# 新闻联播 API

获取央视《新闻联播》每日要闻，支持 JSON / Text / Markdown / Image 四种格式。
数据源：央视官网 tv.cctv.com（无需 AkShare，轻量纯爬虫）。

## API 用法

```
GET /news_cctv                              → 今日 (JSON)
GET /news_cctv?date=20260715                → 指定日期 (JSON)
GET /news_cctv?encoding=text                → 纯文本
GET /news_cctv?encoding=markdown            → Markdown
GET /news_cctv?encoding=image               → PNG 图片
GET /news_cctv?date=20260715&encoding=image  → 指定日期 + 图片
```

---

## 免费部署（三选一）

### 方式一：Render（推荐，最简单）

1. 打开 https://render.com ，用 GitHub 注册登录
2. New → Web Service → 连接你的 GitHub 仓库（先把本目录推上去）
3. 填写：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: `Python 3`
4. 点 Create Web Service
5. 等待部署完成，获得地址如：`https://your-app.onrender.com`
6. 使用：`https://your-app.onrender.com/news_cctv?encoding=image`

> 免费版 15 分钟无访问会休眠，首次请求约 30 秒唤醒。
> 也可以选 Docker 部署（Dockerfile 已准备好），Render 会自动识别。

### 方式二：Railway

1. 打开 https://railway.app ，用 GitHub 登录
2. New Project → Deploy from GitHub repo
3. Railway 自动识别 Dockerfile 并部署
4. 获得地址如：`https://your-app.up.railway.app`
5. 使用：`https://your-app.up.railway.app/news_cctv?encoding=image`

> 每月 $5 免费额度，不休眠。

### 方式三：Docker（任意服务器）

```bash
docker build -t news-cctv-api .
docker run -d -p 8000:8000 news-cctv-api
# 访问 http://localhost:8000/news_cctv?encoding=image
```

---

## 本地运行

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 响应示例（JSON）

```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "date": "20260715",
    "date_display": "2026年7月15日",
    "weekday": "星期三",
    "count": 12,
    "news": [
      {
        "title": "习近平在上海考察时强调...",
        "content": "中共中央总书记...",
        "date": "20260715"
      }
    ]
  }
}
```

## 特性

- ✅ 无需认证，免费使用
- ✅ 不依赖 AkShare/pandas，纯轻量爬虫
- ✅ 支持 JSON / Text / Markdown / Image
- ✅ 10 分钟缓存
- ✅ 数据范围：2016年2月3日至今
- ✅ Docker / Render / Railway 一键部署
