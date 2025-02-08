from fetch import fetch_and_save_wikitext
from database import create_db, save_to_db, month_exists, get_first_n_links
from rewriter import Rewriter
from process_references import process_references
from convert_references import process_json_files
from wiki import get_current_events_links
from loguru import logger
from convert_references import process_json_files


async def main():
    create_db()

    # 获取 2025 年 2 月的新闻链接
    month_page = "February_2025"

    if month_exists(month_page):
        logger.info(f"📌 Database exists. Fetching first 10 links from {month_page}.")
        links = get_first_n_links(month_page, 10)
    else:
        logger.info(f"🔍 Fetching Wikipedia links for {month_page}...")
        links = get_current_events_links(month_page)
        save_to_db(links, month_page)
        links = links[:10]  # 仅取前 10 条

    fetch_and_save_wikitext(links)

    Rewriter.process_folder()

    await process_references()

    await process_json_files()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
