import re
from pathlib import Path
from typing import List

import pywikibot
import requests
from bs4 import BeautifulSoup
from loguru import logger

from database import delete_link, save_to_db, year_exists


@logger.catch
def fetch_and_save_wikitext(
    wikipedia_urls: list[str], output_dir: Path = Path("original")
):
    """
    Fetch Wikipedia page wikitext in bulk and save to the specified directory.

    :param wikipedia_urls: List of Wikipedia page URLs
    :param output_dir: Directory to save files (default: 'original')
    """
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    site = pywikibot.Site("en", "wikipedia")  # Configure Wikipedia site (English)

    for wikipedia_url in wikipedia_urls:
        # Extract page title from URL
        page_title = wikipedia_url.split("/")[-1]
        output_file = output_dir / f"{page_title}.txt"

        # Skip if file already exists
        if output_file.exists():
            # logger.info(f"File '{output_file}' already exists. Skipping...")
            continue

        page = pywikibot.Page(site, page_title)

        if not page.exists():
            logger.warning(f"Page '{page_title}' does not exist. Skipping...")
            continue

        # Fetch wikitext
        wikitext = page.text.strip()

        if len(wikitext) < 200:
            logger.warning(
                f"⚠️ Page '{page_title}' is too short (<200 characters). Skipping..."
            )
            delete_link(page_title)  # Remove invalid link from database
            continue

        # Save wikitext to file
        output_file.write_text(wikitext, encoding="utf-8")
        logger.info(f"Wikitext saved to '{output_file}'")


def get_yearly_events_links(year_page: str) -> list[str]:
    """
    Retrieve links from `<ul>` tags on a Wikipedia year page.

    :param year_page: The Wikipedia year page title (e.g., '2024')
    :return: List of Wikipedia URLs
    """
    url = f"https://en.wikipedia.org/wiki/{year_page}"

    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"❌ Failed to retrieve page: {year_page}")
        return []

    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove links within reflist divs
    for reflist_div in soup.find_all("div", class_="reflist"):
        for a in reflist_div.find_all("a", href=True):
            a.extract()

    # Extract all <ul> tags
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
        r"\d{4}$|"
        r"\d{4}s|"
        r"AD_\d{4}|"
        r"Template:|"
        r"Template_talk|"
        r"Timeline_of|"
        r"File:|"
        r"List_of_.*|"
        r"\d{4}_in_.*|"
        r"\d{1,2}(st|nd|rd|th)_century|"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)_\d{1,2}|"
        r".*#Timeline.*|"
        r".*Olympics.*"
    )

    for ul in ul_tags:
        for link in ul.find_all("a", href=True):
            href = link["href"]
            full_url = f"https://en.wikipedia.org{href}"

            # Keep only Wikipedia internal links, excluding specific patterns
            if href.startswith("/wiki/") and not excluded_patterns.search(href):
                links.append(full_url)

    return links


def scrape_year_events(years: List[str]):
    """Main function to scrape events for multiple years"""
    for year in years:
        if not year_exists(year):
            logger.info(f"Scraping events for {year}")

            # Get event links
            event_links = get_yearly_events_links(year)
            logger.info(f"Found {len(event_links)} links for {year}")

            save_to_db(event_links, year)
