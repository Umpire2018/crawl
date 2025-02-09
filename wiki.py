import requests
from bs4 import BeautifulSoup
import re


def get_yearly_events_links(year_page):
    """获取 Wikipedia `year_page` 页面中的 `<ul>` 下的链接"""
    url = f"https://en.wikipedia.org/wiki/{year_page}"

    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Failed to retrieve page: {year_page}")
        return []

    # 解析 HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # 排除 class="reflist" 所在的 <div> 内的所有链接
    for reflist_div in soup.find_all("div", class_="reflist"):
        for a in reflist_div.find_all("a", href=True):
            a.extract()

    # 提取所有 <ul> 标签
    ul_tags = soup.find_all("ul")

    links = []
    excluded_patterns = re.compile(
        r"Category:|"
        r"Wikipedia:|"
        r"Help:|"
        r"Special:|"
        r"Talk:|"
        r"Portal:|"
        r"Main_Page|"
        r"Contents|"
        r"Community_portal|"
        r"File_upload_wizard|"
        r"MyContributions|"
        r"MyTalk|"
        r"RecentChangesLinked/\d{4}|"
        r"WhatLinksHere/\d{4}|"
        r"\d{4}$|"  # /wiki/2024
        r"\d{4}s|"  # /wiki/2020s
        r"AD_\d{4}|"  # /wiki/AD_2024
        r"Template:|"
        r"Template_talk|"
        r"Timeline_of|"
        r"File:|"
        r"List_of_.*|"  # /wiki/List_of_state_leaders_in_2024
        r"\d{4}_in_.*|"  # /wiki/2024_in_religion
        r"\d{1,2}(st|nd|rd|th)_century|"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)_\d{1,2}|"
        r".*#Timeline.*"
        r".*Olympics.*"
    )

    for ul in ul_tags:
        for link in ul.find_all("a", href=True):
            href = link["href"]
            full_url = f"https://en.wikipedia.org{href}"

            # 只保留 Wikipedia 内部链接，并排除日期、Category 以及特定链接
            if href.startswith("/wiki/") and not excluded_patterns.search(href):
                links.append(full_url)

    return links


# 运行示例
if __name__ == "__main__":
    year_page = "2024"
    event_links = get_yearly_events_links(year_page)
    print(f"Found {len(event_links)} links:")
    for link in event_links[:100]:  # 仅显示前 10 个链接
        print(link)
