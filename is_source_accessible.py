from urllib.parse import urlparse
from loguru import logger


def is_source_accessible(source_url: str, redirected_url: str) -> bool:
    # 提取源 URL 和重定向 URL 的路径
    source_path = urlparse(source_url).path
    redirected_path = urlparse(redirected_url).path

    # 分割路径并过滤空组件
    source_components = [c for c in source_path.split("/") if c]
    redirected_components = [c.lower() for c in redirected_path.split("/") if c]

    # 获取源路径最后一个组件（小写）
    last_component = source_components[-1].lower()

    # 检查是否存在于重定向路径组件中
    if last_component in redirected_components:
        return True
    else:
        logger.warning(
            f"Source URL: {source_url} path component is not found in redirected path: {redirected_url}. Marking as inaccessible."
        )
        return False


# 所有需要测试的 URL
test_urls = [
    (
        "https://www.cnn.com/us/live-news/hawaii-maui-wildfires-08-11-23/index.html",
        "https://edition.cnn.com/us/live-news/hawaii-maui-wildfires-08-11-23/index.html",
    ),
    (
        "https://www.cnn.com/2023/08/10/politics/biden-hawaii-disaster-declaration/index.html",
        "https://edition.cnn.com/2023/08/10/politics/biden-hawaii-disaster-declaration/index.html",
    ),
    (
        "https://www.cnn.com/2023/08/09/us/climate-change-reason-maui-fire/index.html",
        "https://edition.cnn.com/2023/08/09/us/climate-change-reason-maui-fire/index.html",
    ),
    (
        "https://www.cnn.com/2023/08/12/us/hawaii-emergency-warning-system-maui-wildfires/index.html",
        "https://edition.cnn.com/2023/08/12/us/hawaii-emergency-warning-system-maui-wildfires/index.html",
    ),
    (
        "https://www.nfpa.org/News-and-Research/Publications-and-media/Blogs-Landing-Page/NFPA-Today/Blog-Posts/2023/08/12/Maui-wildfire-one-of-deadliest-in-US-history",
        "https://www.nfpa.org/news-blogs-and-articles/blogs/2023/09/19/maui-wildfire-one-of-deadliest-in-us-history",
    ),
    (
        "https://www.msn.com/en-us/weather/topstories/hawaiian-couple-sues-power-companies-over-lahaina-destruction-amid-historic-maui-wildfires/ar-AA1fewOU",
        "https://www.msn.com/zh-hk",
    ),
    (
        "http://www.hawaiitourismauthority.org/news/alerts/maui-and-hawai%CA%BBi-island-wildfire-update/",
        "https://www.hawaiitourismauthority.org/news/alerts/maui-and-hawai%CA%BBi-island-wildfire-update/",
    ),
    (
        "https://www.cnn.com/2023/08/09/weather/maui-county-wildfires-hurricane-dora/index.html",
        "https://edition.cnn.com/2023/08/09/weather/maui-county-wildfires-hurricane-dora/index.html",
    ),
]

# 进行测试并输出结果
for source, redirected in test_urls:
    result = is_source_accessible(source, redirected)
    logger.info(f"Source: {source}\nRedirected: {redirected}\nAccessible: {result}\n")
