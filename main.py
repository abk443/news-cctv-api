"""
新闻联播 API (轻量版) - 无需 AkShare/pandas，直接爬取央视官网
适合部署到 Render / Vercel / Railway 等免费平台

用法：
  GET /news_cctv                          → 今日新闻 (JSON)
  GET /news_cctv?date=20260715            → 指定日期 (JSON)
  GET /news_cctv?encoding=text            → 纯文本
  GET /news_cctv?encoding=markdown        → Markdown
  GET /news_cctv?encoding=image           → PNG 图片
"""

import io
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response, HTMLResponse
from PIL import Image, ImageDraw, ImageFont

app = FastAPI(title="新闻联播 API", version="2.0.0")

# 央视官网数据源
CCTV_LIST_URL = "https://tv.cctv.com/lm/xwlb/day/{date}.shtml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 字体路径（Docker 环境安装的 Noto CJK）
import os
FONT_REGULAR = os.environ.get("FONT_REGULAR", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
FONT_BOLD = os.environ.get("FONT_BOLD", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
# Vercel 环境：bundled font
if not os.path.exists(FONT_REGULAR):
    FONT_REGULAR = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansSC-Regular.otf")
    FONT_BOLD = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansSC-Bold.otf")


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ─── 缓存 ───
_cache: dict = {}


def fetch_news(date_str: str) -> list[dict]:
    """直接爬取央视官网获取新闻联播文字稿"""
    import time
    now = time.time()
    if date_str in _cache:
        ts, data = _cache[date_str]
        if now - ts < 600:
            return data

    url = CCTV_LIST_URL.format(date=date_str)
    news_list = []

    with httpx.Client(timeout=30, headers=HEADERS) as client:
        # 1. 获取当天新闻列表页
        r = client.get(url)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.find_all("li")[1:]  # 跳过第一个

        page_urls = []
        for item in items:
            a = item.find("a")
            if a and a.get("href"):
                page_urls.append(a["href"])

        # 2. 逐条获取新闻内容
        for page_url in page_urls:
            try:
                r2 = client.get(page_url)
                r2.encoding = "utf-8"
                soup2 = BeautifulSoup(r2.text, "lxml")

                # 标题
                if soup2.find("h3"):
                    title = soup2.find("h3").text
                elif soup2.find("div", class_="tit"):
                    title = soup2.find("div", class_="tit").text
                else:
                    continue

                title = title.strip("[视频]").strip().replace("\n", " ")

                # 正文
                if soup2.find("div", class_="cnt_bd"):
                    content = soup2.find("div", class_="cnt_bd").text
                elif soup2.find("div", class_="content_area"):
                    content = soup2.find("div", class_="content_area").text
                else:
                    content = ""

                content = (
                    content.strip()
                    .strip("央视网消息(新闻联播)：")
                    .strip("央视网消息（新闻联播）：")
                    .strip("(新闻联播)：")
                    .strip()
                    .replace("\n", " ")
                )

                if title and content:
                    news_list.append({
                        "title": title,
                        "content": content,
                        "date": date_str,
                    })
            except Exception:
                continue

    _cache[date_str] = (now, news_list)
    return news_list


# ─── 图片生成 ───
def render_image(date_str: str, news_list: list[dict]) -> bytes:
    width = 800
    padding = 40
    max_chars = 36

    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        date_display = f"{dt.year}年{dt.month}月{dt.day}日"
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[dt.weekday()]
    except Exception:
        date_display = date_str
        weekday = ""

    # 计算高度
    height = 120
    for item in news_list:
        height += 30
        content = item["content"]
        lines = []
        for line in content.split("\n"):
            while len(line) > max_chars:
                lines.append(line[:max_chars])
                line = line[max_chars:]
            lines.append(line)
        height += (len(lines) if lines else 1) * (22 + 8)
        height += 25

    height += 40

    img = Image.new("RGB", (width, max(height, 200)), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    # 标题栏
    title_font = _font(FONT_BOLD, 28)
    date_font = _font(FONT_REGULAR, 16)
    item_font = _font(FONT_BOLD, 18)
    body_font = _font(FONT_REGULAR, 15)
    footer_font = _font(FONT_REGULAR, 12)

    draw.rectangle([0, 0, width, 80], fill="#C41E3A")
    draw.text((padding, 18), "新闻联播", font=title_font, fill="#FFFFFF")
    draw.text((padding + 160, 28), date_display, font=date_font, fill="#FFD700")
    draw.text((padding + 320, 28), weekday, font=date_font, fill="#FFD700")

    y = 100
    for i, item in enumerate(news_list, 1):
        draw.text((padding, y), f"{i}. {item['title']}", font=item_font, fill="#1A1A1A")
        y += 30

        content = item["content"]
        lines = []
        for line in content.split("\n"):
            while len(line) > max_chars:
                lines.append(line[:max_chars])
                line = line[max_chars:]
            lines.append(line)

        if not lines:
            lines = [""]

        for line in lines:
            draw.text((padding + 20, y), line, font=body_font, fill="#444444")
            y += 30

        if i < len(news_list):
            draw.line([(padding, y), (width - padding, y)], fill="#EEEEEE", width=1)
            y += 15

    y += 10
    draw.text(
        (padding, y),
        f"共 {len(news_list)} 条新闻 | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        font=footer_font, fill="#999999",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ─── 路由 ───

@app.get("/")
def index():
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新闻联播 API</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#f5f5f5;color:#333}.c{max-width:800px;margin:0 auto;padding:20px}h1{color:#C41E3A;margin:20px 0 10px}.d{color:#666;margin-bottom:30px;line-height:1.8}.e{background:#fff;border-radius:8px;padding:20px;margin-bottom:15px;box-shadow:0 1px 3px rgba(0,0,0,.1)}.e h3{color:#C41E3A;margin-bottom:10px}code{background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:14px}.ex{background:#1e1e1e;color:#d4d4d4;padding:15px;border-radius:6px;margin:10px 0;font-family:monospace;font-size:13px;overflow-x:auto}.m{display:inline-block;background:#61affe;color:#fff;padding:2px 10px;border-radius:4px;font-size:13px;margin-right:10px}</style></head><body><div class="c"><h1>📰 新闻联播 API</h1><p class="d">获取央视《新闻联播》每日要闻，支持 JSON / Text / Markdown / Image<br>数据来源：央视官网 tv.cctv.com · 无需认证 · 免费使用</p><div class="e"><h3><span class="m">GET</span> /news_cctv</h3><p><code>date</code>（可选）：YYYYMMDD，默认今天</p><p><code>encoding</code>（可选）：json / text / markdown / image，默认 json</p><div class="ex">GET /news_cctv<br>GET /news_cctv?date=20260715<br>GET /news_cctv?encoding=image<br>GET /news_cctv?date=20260715&encoding=markdown</div></div><div class="e"><h3>部署</h3><p>Render / Railway / Vercel / Docker 均可部署，详见 README.md</p></div></div></body></html>"""
    return HTMLResponse(content=html)


@app.get("/news_cctv")
def get_news(
    date: Optional[str] = Query(default=None),
    encoding: str = Query(default="json"),
):
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    date = date.strip().replace("-", "").replace("/", "")

    if len(date) != 8 or not date.isdigit():
        return JSONResponse(status_code=400, content={"code": 400, "message": "日期格式错误，请用 YYYYMMDD，如 20260715", "data": None})

    try:
        news_list = fetch_news(date)
    except Exception as e:
        return JSONResponse(status_code=500, content={"code": 500, "message": f"获取失败: {str(e)}", "data": None})

    if not news_list:
        return JSONResponse(content={"code": 404, "message": f"{date} 新闻联播内容尚未发布", "data": None})

    try:
        dt = datetime.strptime(date, "%Y%m%d")
        date_display = f"{dt.year}年{dt.month}月{dt.day}日"
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[dt.weekday()]
    except Exception:
        date_display, weekday = date, ""

    if encoding == "json":
        return {"code": 200, "message": "获取成功", "data": {"date": date, "date_display": date_display, "weekday": weekday, "count": len(news_list), "news": news_list}}

    elif encoding == "text":
        lines = [f"新闻联播 {date_display} {weekday}", "=" * 40, ""]
        for i, n in enumerate(news_list, 1):
            lines.append(f"{i}. {n['title']}")
            lines.append(f"   {n['content']}")
            lines.append("")
        lines.append(f"共 {len(news_list)} 条新闻")
        return PlainTextResponse("\n".join(lines))

    elif encoding == "markdown":
        lines = [f"# 新闻联播 {date_display} {weekday}", ""]
        for i, n in enumerate(news_list, 1):
            lines.append(f"## {i}. {n['title']}")
            lines.append("")
            lines.append(n["content"])
            lines.append("")
        lines.append(f"\n---\n*共 {len(news_list)} 条新闻*")
        return PlainTextResponse("\n".join(lines), media_type="text/markdown")

    elif encoding == "image":
        try:
            return Response(content=render_image(date, news_list), media_type="image/png")
        except Exception as e:
            return JSONResponse(status_code=500, content={"code": 500, "message": f"图片生成失败: {str(e)}", "data": None})

    else:
        return JSONResponse(status_code=400, content={"code": 400, "message": f"不支持: {encoding}，可选: json / text / markdown / image", "data": None})


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
