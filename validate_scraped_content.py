import openai
from pydantic import BaseModel
from web_scraper import AsyncWebScraper


class ValidationResult(BaseModel):
    url: str
    valid: bool


class ValidationResults(BaseModel):
    results: list[ValidationResult]


def validate_scraped_content(scraped_data: str) -> ValidationResult:
    prompt = f"""You are an assistant that validates web page content.

Given the following URLs and its scraped content, determine whether the content is valid and relevant.
Provide your answer in JSON format with the following keys:
- url: The URL of the web page.
- valid: A boolean indicating whether the content is valid.

Content:
{scraped_data}

Please only output the JSON."""

    client = openai.OpenAI(
        api_key="sk-lZJJXTQBqXjZyWGllgn2XA2zogxxjNbU74fKln62OmkSJm9m",
        base_url="https://happyapi.org/v1",
    )
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # 使用 GPT-4o-mini 模型
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that validates web page content.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format=ValidationResults,
    )
    result = ValidationResults.model_validate(completion.choices[0].message.parsed)

    return result


class WebContentValidator:
    def __init__(self, urls: list[str]):
        self.urls = urls

    async def validate(self) -> str:
        content = await AsyncWebScraper.scrape(self.urls)
        validation_results = validate_scraped_content(content)
        return validation_results
