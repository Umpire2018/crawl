from fetch import fetch_and_save_wikitext
from database import get_filtered_links
from rewriter import Rewriter
from process_references import process_references
from convert_references import process_json_files

async def main():
    db_url = "sqlite:///articles.db"
    links = get_filtered_links(db_url)

    fetch_and_save_wikitext(links)

    Rewriter.process_folder()

    await process_references()

    await process_json_files()

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
