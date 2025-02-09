from fetch import fetch_and_save_wikitext
from database import create_db, save_to_db, year_exists, get_first_n_links
from rewriter import Rewriter
from process_references import process_references
from convert_references import process_json_files
from wiki import get_yearly_events_links
from loguru import logger
from convert_references import process_json_files


async def main():
    create_db()

    year = "2024"

    if year_exists(year):
        logger.info(f"📌 Database exists. Fetching first 10 links from {year}.")
        links = get_first_n_links(year)
    else:
        logger.info(f"🔍 Fetching Wikipedia links for {year}...")
        links = get_yearly_events_links(year)
        save_to_db(links, year)

    links = links[:4]

    fetch_and_save_wikitext(links)

    Rewriter.process_folder()

    await process_references()

    await process_json_files()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
