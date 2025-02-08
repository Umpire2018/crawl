import requests
import re
from bs4 import BeautifulSoup


def get_current_events_links(month_page):
    """获取 Wikipedia `Portal:Current events/YYYY_Month` 页面中的 `current-events` 下的链接"""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "format": "json",
        "page": f"Portal:Current events/{month_page}",
        "prop": "text",
        "redirects": True,
    }

    response = requests.get(url, params=params)
    data = response.json()

    if "parse" not in data:
        print(f"❌ Failed to retrieve page: {month_page}")
        return []

    # 解析 HTML
    html_content = data["parse"]["text"]["*"]
    soup = BeautifulSoup(html_content, "html.parser")

    # 提取 `class="current-events"` 的 <div>
    current_events_divs = soup.find_all("div", class_="current-events")

    links = []
    for div in current_events_divs:
        for link in div.find_all("a", href=True):
            href = link["href"]

            # 只保留 Wikipedia 内部链接
            if href.startswith("/wiki/") and not re.search(
                r":", href
            ):  # 过滤 `Special:`, `File:`, `Help:` 等
                full_url = f"https://en.wikipedia.org{href}"
                links.append(full_url)

    return links
