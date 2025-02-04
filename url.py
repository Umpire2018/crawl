from typing import List, Dict
from niquests import Session
from models import CitationData, DocPage, DocSection, DocBlock
from niquests.exceptions import RequestException, SSLError, ConnectTimeout
import time
from loguru import logger


def process_references(doc_page: DocPage):
    """
    Process all references in a DocPage, replacing reference strings with CitationData objects.
    """
    # Collect all citations from the entire document
    all_citations: List[CitationData] = []

    def traverse_content(content):
        if isinstance(content, DocSection):
            for item in content.content:
                traverse_content(item)
        elif isinstance(content, DocBlock):
            for sentence in content.sentences:
                all_citations.extend(sentence.references)

    for section in doc_page.content:
        traverse_content(section)

    # Limit to the first 10 URLs for testing (optional)
    all_citations = all_citations[:10]

    # Create a multiplexed session using niquests
    s = Session(multiplexed=True)

    # Dictionary to map each lazy response to its corresponding CitationData.
    response_mapping: Dict = {}

    # Start timing
    start_time = time.time()

    # For each citation data with a non-None URL, issue a GET request.
    for data in all_citations:
        if data.url:
            try:
                req = s.get(data.url)
                response_mapping[req] = data
            except SSLError as e:
                logger.error(f"SSL Error for URL (no proxy): {data.url} - {e}")
                data.accessible = False  # Mark as inaccessible
            except ConnectTimeout as e:
                # Handle the timeout specifically
                logger.error(f"Connection Timeout for URL: {data.url} - {e}")
                data.accessible = False

    # Issue concurrent requests and wait until all responses are ready.
    s.gather()

    # End timing
    end_time = time.time()
    logger.info(f"Time taken to check URLs: {end_time - start_time:.2f} seconds")

    # Update each CitationData object's 'accessible' field based on its HTTP status code.
    for req, data in response_mapping.items():
        try:
            # The response is "lazy" until we access an attribute such as status_code.
            data.accessible = req.status_code == 200
        except RequestException:
            data.accessible = False

    # Update the document with the processed citations
    def update_content(content):
        if isinstance(content, DocSection):
            for item in content.content:
                update_content(item)
        elif isinstance(content, DocBlock):
            for sentence in content.sentences:
                # 直接修改引用对象，确保 accessible 字段正确存储
                for ref in sentence.references:
                    for processed_ref in all_citations:
                        if ref.url == processed_ref.url:
                            ref.accessible = (
                                processed_ref.accessible
                            )  # 直接更新 `accessible`

    for section in doc_page.content:
        update_content(section)


def main():
    input_file_path = "wikitext.json"
    output_file_path = "wikitext_with_url_test.json"

    with open(input_file_path, "r", encoding="utf-8") as f:
        doc_json = f.read()

    doc_page = DocPage.model_validate_json(doc_json)

    process_references(doc_page)

    with open(output_file_path, "w", encoding="utf-8") as fw:
        fw.write(doc_page.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
