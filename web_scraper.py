import asyncio
import re
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, model_serializer

from loguru import logger


class ScrapedData(BaseModel):
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    error: Optional[str] = None


class ScrapedDataList(BaseModel):
    data: List[ScrapedData] = Field(default_factory=list)
    max_content_length: int = 5000  # Max length for individual content
    max_output_length: int = 100000  # Max length for the entire serialized result

    @model_serializer
    def ser_model(self) -> str:
        # List to store concatenated strings
        result = []

        for data in self.data:
            if data.error:
                continue

            assert data.content is not None

            # Truncate content to ensure it does not exceed max_content_length
            if len(data.content) > self.max_content_length:
                data.content = (
                    data.content[: self.max_content_length] + "[TOO LONG, END]"
                )

            result.append(
                f"URL: {data.url}\nTitle: {data.title}\nContent:\n{data.content}\n"
            )

        output = "\n---\n".join(result)

        # Apply final length truncation to the overall result
        if len(output) > self.max_output_length:
            output = output[: self.max_output_length] + "\n[OUTPUT TOO LONG, TRUNCATED]"

        return output


class AsyncWebScraper:
    @staticmethod
    async def scrape(urls: List[str]):
        """
        Scrapes content from a list of webpages asynchronously.

        Args:
            urls (List[str]): A list of URLs to scrape.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        async def fetch_url(url: str) -> ScrapedData:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, timeout=10)

                    if response.status_code != 200:
                        return ScrapedData(
                            url=url,
                            error=f"HTTP {response.status_code}: {response.reason_phrase}",
                        )

                    html = response.text
                    soup = BeautifulSoup(html, "html.parser")

                    # Remove script and style elements
                    for script in soup(["script", "style", "meta", "noscript"]):
                        script.decompose()

                    # Extract content based on specified elements or automatic content detection
                    main_content = (
                        soup.find("main")
                        or soup.find("article")
                        or soup.find("div", class_=re.compile(r"content|main|article"))
                    )
                    if main_content:
                        # Extract main content text and split into lines
                        content_lines = main_content.get_text(strip=True).splitlines()
                    else:
                        # Extract text from all <p> elements
                        content_lines = [
                            p.get_text(strip=True) for p in soup.find_all("p")
                        ]

                    # Clean up the content
                    content_lines = [
                        re.sub(r"\s+", " ", c).strip() for c in content_lines
                    ]

                    # If content_lines is empty, provide a default value
                    if not content_lines:
                        content = "No content available"
                    else:
                        # Combine the list of lines into a single string
                        content = "\n".join(content_lines)

                    return ScrapedData(
                        url=url,
                        title=soup.title.string if soup.title else "Untitled",
                        content=content,
                    )
            except Exception as e:
                return ScrapedData(url=url, error=f"Error: {str(e)}")

        scraped_data = await asyncio.gather(*(fetch_url(url) for url in urls))

        # Wrap results in ScrapedDataList
        result = ScrapedDataList(data=scraped_data).model_dump()
        logger.info(f"Scraped data:\n{result}")
        return result


if __name__ == "__main__":
    # List of URLs to scrape
    urls = [
        "https://www.hawaiitourismauthority.org/news/alerts/maui-and-hawai%CA%BBi-island-wildfire-update/"
    ]
    asyncio.run(AsyncWebScraper.scrape(urls))
