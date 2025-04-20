from __future__ import annotations

import asyncio
import re
import ssl
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

import aiohttp
import certifi
from aiohttp import ClientError, ClientTimeout
from aiohttp.resolver import AsyncResolver
from loguru import logger

from models import CitationData, DocBlock, DocPage, DocSection, DocSentence


class WikiTextParser:
    """Handles parsing of Wikipedia-style text content into structured document format."""

    @staticmethod
    def extract_and_remove_references(x: str) -> Tuple[str, List[str]]:
        """
        提取并移除文本中 <ref>...</ref> 的引用内容。
        返回值：
          - cleaned: 去除引用标记后的文本
          - found:   所有被匹配到的引用列表
        """
        pattern = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL)
        found = pattern.findall(x)
        cleaned = pattern.sub("", x).strip()
        return cleaned, found

    @staticmethod
    def split_sentences(x: str) -> List[str]:
        """
        根据 '。' 来简单切分文本为句子。
        如果 '。' 少于等于 1 个，则直接返回整个文本。
        """
        n = x.count("。")
        if n <= 1:
            return [x]
        return re.split(r"(?<=。){1}", x, maxsplit=n - 1)

    @staticmethod
    def parse_citation(citation: str) -> CitationData:
        """
        Extracts metadata from citation string.

        Args:
            citation: Raw citation text from Wikipedia

        Returns:
            CitationData object with extracted URL and type
        """

        text = citation

        # Extract the main URL using regex
        url_match = re.search(r"\| *url=(https?://[^|\s]+)", citation)
        url = url_match.group(1) if url_match else None

        # Extract the type from the citation
        type_match = re.search(r"\{\{Cite\s+(\w+)", citation) or re.search(
            r"\{\{cite\s+(\w+)", citation
        )
        type_value = type_match.group(1) if type_match else None

        return CitationData(text=text, url=url, type=type_value)

    @staticmethod
    def create_text_blocks(x: str, sid: str, sc: int) -> Tuple[List[DocBlock], int]:
        """
        将原始文本按双换行分段，再按 cut_sentences 拆分为句子，构建 DocBlock。
        每个句子中可能包含引用信息，需要在此处拆解并记录。

        参数：
          - x:   待处理的文本段
          - sid: 当前章节（或上层标识）的字符串ID
          - sc:  计数器，用于给句子生成新的ID

        返回值：
          - blocks: 生成的 DocBlock 列表（在本函数内通常只生成一个，装入句子）
          - sc:     更新后的计数器
        """
        paragraphs = x.split("\n\n")
        sentence_list = []

        for p in paragraphs:
            # 去除 File: 标记及内部链接，如 [[File:xxx]] 或 [[yyy]]
            p_clean = re.sub(r"\[\[File:.*?\]\]", "", p, flags=re.IGNORECASE)
            p_clean = re.sub(r"\[\[(.*?)\]\]", r"\1", p_clean)

            for s in WikiTextParser.split_sentences(p_clean):
                cleaned, refs = WikiTextParser.extract_and_remove_references(s)
                # 只有在句子中真正检测到引用才添加
                if not refs:
                    continue
                sentence_list.append(
                    DocSentence(
                        id=f"{sid}.s{sc}",
                        text=cleaned,
                        references=[WikiTextParser.parse_citation(ref) for ref in refs],
                    )
                )
                sc += 1

        return [DocBlock(sentences=sentence_list)], sc

    @staticmethod
    def section_parse(
        x: str, pid: str, lvl: int, stk=None
    ) -> list[DocSection | DocBlock]:
        """
        递归解析文本中的章节结构，包括子章节和文本块。
        参数：
          - x:    剩余待解析的文本
          - pid:  父章节ID或顶层ID
          - lvl:  当前标题层级（用于判断是否需要退栈）
          - stk:  堆栈，用于维护章节层级
        返回：
          - 解析后得到的一系列 DocSection 或 DocBlock
        """
        if stk is None:
            stk = []

        # 匹配形如 "== 标题 ==" 这样的行，用于拆分章节
        pattern = re.compile(r"^\s*(={2,6})\s*([^=]+?)\s*\1\s*$", re.MULTILINE)
        matches = list(pattern.finditer(x))

        result: list[DocSection | DocBlock] = []
        sc = 1
        prev_end = 0

        for i, match in enumerate(matches):
            start = match.start()
            # 先处理标题行前面的普通文本，作为一个或多个 DocBlock
            if start > prev_end:
                seg = x[prev_end:start].strip()
                if seg:
                    blocks, sc = WikiTextParser.create_text_blocks(seg, pid, sc)
                    if stk:
                        stk[-1]["sec"].content.extend(blocks)
                    else:
                        result.extend(blocks)

            # 当前标题层级
            current_level = len(match.group(1))
            # 若当前标题层级 <= 栈顶层级，则退栈
            while stk and stk[-1]["lvl"] >= current_level:
                stk.pop()

            # 新的章节ID，根据上下文生成
            new_id = (
                f"{pid}.{len(result) + 1}"
                if not stk
                else f"{stk[-1]['sec'].id}.{len(stk[-1]['sec'].content) + 1}"
            )

            # 创建新的章节对象
            sec = DocSection(id=new_id, title=match.group(2).strip(), content=[])

            # 加入 result 或者父章节的 content 中
            if stk:
                stk[-1]["sec"].content.append(sec)
            else:
                result.append(sec)

            # 将本章节压入栈，用于处理其子内容
            stk.append({"lvl": current_level, "sec": sec})

            # 继续处理本章节到下一标题之间的文本
            nxt = matches[i + 1].start() if (i + 1 < len(matches)) else len(x)
            sub_txt = x[match.end() : nxt].strip()
            if sub_txt:
                sec.content.extend(
                    WikiTextParser.section_parse(sub_txt, new_id, current_level, stk)
                )
            prev_end = nxt

        # 若最后一个标题之后还有文本，则构建 DocBlock
        if prev_end < len(x):
            tail = x[prev_end:].strip()
            if tail:
                blocks, sc = WikiTextParser.create_text_blocks(tail, pid, sc)
                if stk:
                    stk[-1]["sec"].content.extend(blocks)
                else:
                    result.extend(blocks)

        return result

    @staticmethod
    def replace_info(content: str) -> str:
        """
        Finds the first occurrence of '==(any content)==' (heading).
        Searches upwards for the last '}}' before that heading.
        Replaces that '}}' line with '== Preface ==' and removes all content above it.
        """
        # Find the first heading like "== Some Section =="
        heading_match = re.search(r"^==.*==\s*$", content, re.MULTILINE)
        if not heading_match:
            return content  # No heading found, return original text

        heading_start = heading_match.start()

        # Improved regex: Matches '}}' that may appear anywhere (not just on its own line)
        closing_braces = list(re.finditer(r"\}\}\s*(?:\n|$)", content[:heading_start]))

        if not closing_braces:
            return content  # No '}}' found before heading, return original text

        last_closing_brace = closing_braces[-1]  # Get the last occurrence of '}}'

        # Replace the found '}}' position with '== Preface ==' and remove all content above it
        return "== Preface ==\n" + content[last_closing_brace.end() :]

    @staticmethod
    def parse_file(file_path: Path) -> str:
        """
        Reads a .txt file, extracts its title, processes sections and text blocks, and returns a JSON string.
        """
        file_content = file_path.read_text(encoding="utf-8")
        doc_title = file_path.stem  # Get filename without extension
        cleaned_content = WikiTextParser.replace_info(file_content)

        # Match top-level headings like "== Section Name =="
        section_pattern = re.compile(r"^\s*==\s*([^=]+?)\s*==\s*$", re.MULTILINE)
        section_matches = list(section_pattern.finditer(cleaned_content))

        sections = []
        for i, heading in enumerate(section_matches):
            heading_text = heading.group(1).strip()
            start_idx = heading.end()
            end_idx = (
                section_matches[i + 1].start()
                if (i + 1 < len(section_matches))
                else len(cleaned_content)
            )
            section_text = cleaned_content[start_idx:end_idx].strip()

            # Parse sub-sections recursively
            parsed_content = WikiTextParser.section_parse(section_text, str(i + 1), 2)
            sections.append(
                DocSection(id=str(i + 1), title=heading_text, content=parsed_content)
            )

        doc = DocPage(title=doc_title, content=sections)
        return doc.model_dump_json(indent=2)


class CitationProcessor:
    """Handles processing and validation of document citations."""

    @staticmethod
    def is_redirect_invalid(original_url: str, final_url: str) -> bool:
        """
        Checks if a redirect leads to an invalid destination.

        Args:
            original_url: Initial URL requested
            final_url: URL after redirects

        Returns:
            True if redirect goes to different domain's root page
        """
        final = urlparse(str(final_url))
        return final.netloc != urlparse(str(original_url)).netloc and final.path == "/"

    async def process_document_citations(self, document: DocPage) -> None:
        """
        Processes all citations in a document asynchronously.

        Args:
            document: Document page to process
        """
        start_time = asyncio.get_event_loop().time()

        citations = self._collect_citations(document)
        stats = await self._validate_citations(citations)
        self._log_validation_results(stats)

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"Citation processing completed in {elapsed:.2f} seconds")

    def _collect_citations(self, document: DocPage) -> List[CitationData]:
        """Recursively gathers all citations from document structure."""
        citations = []

        def traverse(node):
            match node:
                case DocSection(content=children):
                    for child in children:
                        traverse(child)
                case DocBlock(sentences=sentences):
                    for sentence in sentences:
                        citations.extend(sentence.references)

        for section in document.content:
            traverse(section)

        return citations

    async def _validate_citations(
        self, citations: List[CitationData]
    ) -> dict[str, int]:
        """
        Validates citation URLs asynchronously.

        Args:
            citations: List of citations to validate

        Returns:
            Dictionary with validation statistics
        """
        stats = {"valid": 0, "invalid": 0, "redirected": 0}

        timeout = ClientTimeout(
            total=20,  # 严格控制总时间
            connect=10,  # 快速失败
            sock_read=10,  # 避免慢响应阻塞并发
        )
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        resolver = AsyncResolver(nameservers=["8.8.8.8", "1.1.1.1"])
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            ttl_dns_cache=300,  # DNS缓存5分钟
            limit=200,  # 总连接数限制
            resolver=resolver,
        )

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            max_line_size=16384,
            max_field_size=16384,
        ) as session:
            await asyncio.gather(
                *(
                    self._check_citation(session, citation, stats)
                    for citation in citations
                    if citation.url
                )
            )

        return stats

    async def _check_citation(
        self,
        session: aiohttp.ClientSession,
        citation: CitationData,
        stats: dict[str, int],
    ) -> None:
        """Performs validation of a single citation."""
        if "archive.org" in citation.url:
            self._mark_archive_url(citation, stats)
            return

        try:
            async with session.get(citation.url) as response:
                await self._process_citation_response(response, citation, stats)
        except (ClientError, asyncio.TimeoutError) as error:
            self._record_citation_error(error, citation, stats)

    def _mark_archive_url(self, citation: CitationData, stats: dict[str, int]) -> None:
        """Handles special case for archive.org URLs."""
        citation.status_code = 403
        citation.reason = "Blocked: Archive.org URL"
        stats["invalid"] += 1
        logger.debug(f"Skipped archive.org link: {citation.url}")

    async def _process_citation_response(
        self,
        response: aiohttp.ClientResponse,
        citation: CitationData,
        stats: dict[str, int],
    ) -> None:
        """Processes and validates HTTP response for citation."""
        citation.status_code = response.status

        if response.status == 200:
            if response.history and self.is_redirect_invalid(
                citation.url, str(response.url)
            ):
                citation.status_code = 403
                citation.reason = "Invalid redirect destination"
                stats["invalid"] += 1
            else:
                citation.url = str(response.url)
                stats["valid"] += 1
                if response.history:
                    stats["redirected"] += 1
        else:
            citation.reason = response.reason
            stats["invalid"] += 1

    def _record_citation_error(
        self, error: Exception, citation: CitationData, stats: dict[str, int]
    ) -> None:
        """Records error information for failed citation check."""
        error_msg = (
            str(error) if not isinstance(error, asyncio.TimeoutError) else "Timeout"
        )
        logger.warning(f"Citation check failed for {citation.url}: {error_msg}")

        citation.status_code = None
        citation.reason = error_msg
        stats["invalid"] += 1

    def _log_validation_results(self, stats: dict[str, int]) -> None:
        """Logs summary of citation validation results."""
        total = stats["valid"] + stats["invalid"]
        logger.info(
            f"Citation validation complete - "
            f"Total: {total}, Valid: {stats['valid']}, "
            f"Invalid: {stats['invalid']}, Redirected: {stats['redirected']}"
        )

    async def process_document_file(self, source_file: Path, output_dir: Path) -> None:
        """
        Processes citations in a single document file.

        Args:
            source_file: Path to source document
            output_dir: Directory for processed output
        """
        logger.info(f"Processing document: {source_file.name}")

        try:
            document = DocPage.model_validate_json(
                WikiTextParser.parse_file(source_file)
            )

            await self.process_document_citations(document)

            output_file = output_dir / f"{source_file.stem}.json"

            output_file.write_text(document.model_dump_json(indent=2), encoding="utf-8")
            logger.success(f"Saved processed document: {output_file.name}")

        except Exception:
            logger.exception(f"Failed to process {source_file.name}")


async def process_wiki_documents(
    test_mode: bool = False,
) -> None:
    """
    Main workflow for processing Wikipedia documents:
    1. Finds unprocessed files in source directory
    2. Validates and updates citations
    3. Saves processed files to output directory
    """
    processor = CitationProcessor()

    source_dir = Path("original")
    output_dir = Path("processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create mapping of document names to files
    source_documents = {
        file.stem: file for file in source_dir.iterdir() if file.is_file()
    }

    # Get already processed documents
    processed_documents = {file.stem for file in output_dir.iterdir() if file.is_file()}

    # Find documents needing processing
    unprocessed = set(source_documents.keys()) - processed_documents

    if not unprocessed:
        logger.info("All documents already processed - nothing to do")
        return

    # TEST MODE: Only take the first document
    if test_mode:
        unprocessed = set([next(iter(unprocessed))])  # 取第一个元素
        logger.info(f"TEST MODE: Processing only first document - {unprocessed}")

        # Delete corresponding output file if exists
        doc_name = next(iter(unprocessed))
        output_file = output_dir / f"{doc_name}.json"
        if output_file.exists():
            output_file.unlink()
            logger.info(f"Deleted existing output file: {output_file}")

    logger.info(f"Found {len(unprocessed)} documents to process")

    # Process each document
    for document_name in unprocessed:
        await processor.process_document_file(
            source_file=source_documents[document_name], output_dir=output_dir
        )


if __name__ == "__main__":
    asyncio.run(process_wiki_documents(test_mode=True))
