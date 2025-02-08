import asyncio
import httpx
from models import CitationData, DocPage, DocSection, DocBlock
from loguru import logger
import time
from typing import List
from validate_scraped_content import WebContentValidator, ValidationResults
from pathlib import Path

MAX_CONCURRENT_REQUESTS = 10  # 设置最大并发 HTTP 请求数

async def fetch_and_map_with_semaphore(semaphore, client, data, counts, redirected_urls):
    """受 Semaphore 限制的异步请求"""
    async with semaphore:  
        await fetch_and_map(client, data, counts, redirected_urls)

async def process_references_async(doc_page: DocPage):
    """
    Process all references in a DocPage asynchronously, replacing reference strings with CitationData objects.
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
    all_citations = all_citations[:-1]

    # Create an asynchronous HTTP client using httpx with timeout of 5 seconds
    async with httpx.AsyncClient(follow_redirects=True, http2=True,timeout=5) as client:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)  # 限制最大并发请求数

        tasks = []
        counts = {"success": 0, "failure": 0}  # Use a dictionary to track counts
        redirected_urls = []  # Store URLs that were redirected

        # For each citation data with a non-None URL, issue an asynchronous GET request.
        for data in all_citations:
            if data.url:
                tasks.append(fetch_and_map_with_semaphore(semaphore, client, data, counts, redirected_urls))

        # Start timing
        start_time = time.time()

        # Run all tasks concurrently and wait for completion
        await asyncio.gather(*tasks)

        # End timing
        end_time = time.time()
        logger.info(f"Time taken to check URLs: {end_time - start_time:.2f} seconds")

        # Perform secondary validation only for redirected URLs
        if redirected_urls:
            logger.info("Performing secondary validation for redirected URLs...")
            validator = WebContentValidator(redirected_urls)
            validation_results: ValidationResults = await validator.validate()

            print(validation_results.model_dump_json(indent=2))

            for result in validation_results.results:
                for citation in all_citations:
                    if citation.url == result.url:
                        citation.accessible = result.valid
                        if result.valid:
                            counts["success"] += 1
                            counts["failure"] -= (
                                1  # Adjust failure count if validated successfully
                            )

        # Output total count, success and failure counts
        logger.info(f"Total checked URLs: {len(all_citations)}")
        logger.info(f"Successful checks: {counts['success']}")
        logger.info(f"Failed checks: {counts['failure']}")

        # Update the document with the processed citations
        await update_content_async(doc_page, all_citations)



async def fetch_and_map(client, data, counts, redirected_urls):
    try:
        # Send the GET request asynchronously with timeout of 5 seconds
        req = await client.get(data.url)

        # Check the final destination and redirection history
        original_url = data.url  # The original URL (before redirect)
        final_url = str(req.url)  # The final URL (after following all redirects)

        # Compare if the URL was redirected
        if original_url != final_url:
            logger.info(f"Original URL {original_url} was redirected to {final_url}")
            # Update the CitationData object's URL to the final redirected URL
            data.url = final_url
            redirected_urls.append(final_url)  # Store for secondary validation

        # Update accessibility based on final response status code
        if req.status_code == 200:
            data.accessible = True
            counts["success"] += 1
        else:
            data.accessible = False
            counts["failure"] += 1

    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError):
        data.accessible = False
        counts["failure"] += 1


async def update_content_async(doc_page, all_citations):
    async def update_content(content):
        if isinstance(content, DocSection):
            for item in content.content:
                await update_content(item)
        elif isinstance(content, DocBlock):
            for sentence in content.sentences:
                for ref in sentence.references:
                    for processed_ref in all_citations:
                        if (
                            ref.url == processed_ref.url
                        ):  # Match by updated URL (if redirected)
                            ref.accessible = processed_ref.accessible

    for section in doc_page.content:
        await update_content(section)


async def process_references(input_dir: Path = Path("processed"), output_dir: Path = Path("processed")):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)  # 确保输出目录存在

    json_files = list(input_path.glob("*.json"))  # 获取所有 .json 文件

    if not json_files:
        logger.warning("❌ No JSON files found in the input directory.")
        return

    for json_file in json_files:
        logger.info(f"📌 Processing file: {json_file.name}")
        await process_single_file(json_file, output_path)  # **同步调用**
        logger.info(f"✅ Finished processing: {json_file.name}")



async def process_single_file(input_file: Path, output_path: Path):
    """
    处理单个 JSON 文件，解析并保存处理后的结果。

    :param input_file: 输入的 JSON 文件路径
    :param output_path: 解析后的 JSON 文件的保存路径
    """
    output_file = output_path / f"{input_file.stem}_url_test.json"

    # **检查文件是否已处理过**
    if output_file.exists():
        logger.info(f"📌 Skipping {input_file.name} (already processed: {output_file.name})")
        return  # **直接返回，不再处理**

    logger.info(f"🔍 Processing file: {input_file.name}")

    # 读取 JSON 文件
    with open(input_file, "r", encoding="utf-8") as f:
        doc_json = f.read()

    # 解析为 DocPage 对象
    doc_page = DocPage.model_validate_json(doc_json)

    await process_references_async(doc_page)

    # 保存处理后的 JSON 文件
    with open(output_file, "w", encoding="utf-8") as fw:
        fw.write(doc_page.model_dump_json(indent=2))

    logger.info(f"✅ Processed and saved: {output_file}")

