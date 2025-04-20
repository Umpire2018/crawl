from citation_processor import process_wiki_documents
from convert_references import transform_json_files
from database import create_db, get_first_n_links
from wikipedia_yearly_events_scraper import fetch_and_save_wikitext, scrape_year_events


async def main():
    create_db()

    years = ["2023", "2024", "2025"]

    scrape_year_events(years=years)

    links = get_first_n_links()

    fetch_and_save_wikitext(links)

    await process_wiki_documents()

    transform_json_files()


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted by user")
