import pywikibot
from pathlib import Path
from loguru import logger


@logger.catch
def fetch_and_save_wikitext(
    wikipedia_urls: list[str], output_dir: Path = Path("original")
):
    """
    批量获取 Wikipedia 页面 Wikitext 并保存到指定目录。

    :param wikipedia_urls: 包含 Wikipedia 页面 URL 的列表
    :param output_dir: 保存文件的目录（默认：original_text）
    """
    output_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在

    site = pywikibot.Site("zh", "wikipedia")  # 配置 Wikipedia 站点（简体中文）

    for wikipedia_url in wikipedia_urls:
        # 从 URL 提取页面标题
        page_title = wikipedia_url.split("/")[-1]
        output_file = output_dir / f"{page_title}.txt"

        # 如果文件已存在，则跳过
        if output_file.exists():
            logger.info(f"File '{output_file}' already exists. Skipping...")
            continue

        page = pywikibot.Page(site, page_title)

        if not page.exists():
            logger.warning(f"Page '{page_title}' does not exist. Skipping...")
            continue

        # 获取 Wikitext
        wikitext = page.text

        # 保存 Wikitext 到文件
        output_file.write_text(wikitext, encoding="utf-8")

        logger.success(f"Wikitext saved to '{output_file}'")
