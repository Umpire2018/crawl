from __future__ import annotations
import re
from typing import List, Tuple
from models import DocBlock, DocPage, DocSection, DocSentence, CitationData
from pathlib import Path
from loguru import logger


class Rewriter:
    @staticmethod
    def ref_split(x: str) -> Tuple[str, List[str]]:
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
    def cut_sentences(x: str) -> List[str]:
        """
        根据 '。' 来简单切分文本为句子。
        如果 '。' 少于等于 1 个，则直接返回整个文本。
        """
        n = x.count("。")
        if n <= 1:
            return [x]
        return re.split(r"(?<=。){1}", x, maxsplit=n - 1)

    @staticmethod
    def extract_data(citation: str) -> CitationData:
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
    def block_build(x: str, sid: str, sc: int) -> Tuple[List[DocBlock], int]:
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

            for s in Rewriter.cut_sentences(p_clean):
                cleaned, refs = Rewriter.ref_split(s)
                # 只有在句子中真正检测到引用才添加
                if not refs:
                    continue
                sentence_list.append(
                    DocSentence(
                        id=f"{sid}.s{sc}",
                        text=cleaned,
                        references=[Rewriter.extract_data(ref) for ref in refs],
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
                    blocks, sc = Rewriter.block_build(seg, pid, sc)
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
                    Rewriter.section_parse(sub_txt, new_id, current_level, stk)
                )
            prev_end = nxt

        # 若最后一个标题之后还有文本，则构建 DocBlock
        if prev_end < len(x):
            tail = x[prev_end:].strip()
            if tail:
                blocks, sc = Rewriter.block_build(tail, pid, sc)
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
        cleaned_content = Rewriter.replace_info(file_content)

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
            parsed_content = Rewriter.section_parse(section_text, str(i + 1), 2)
            sections.append(
                DocSection(id=str(i + 1), title=heading_text, content=parsed_content)
            )

        doc = DocPage(title=doc_title, content=sections)
        return doc.model_dump_json(indent=2)

    @staticmethod
    def process_folder(
        input_dir: Path = Path("original"), output_dir: Path = Path("processed")
    ):
        """
        Processes all .txt files in `input_dir`, parses them, and saves the JSON output in `output_dir`.
        """
        output_dir.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists

        for txt_file in input_dir.glob("*.txt"):
            try:
                # Parse file and generate JSON output
                json_output = Rewriter.parse_file(txt_file)

                # Define output file path (.json instead of .txt)
                output_file = output_dir / f"{txt_file.stem}.json"

                # Save JSON output
                output_file.write_text(json_output, encoding="utf-8")

                logger.success(f"✅ Saved parsed file: {output_file}")

            except Exception as e:
                logger.exception(f"❌ Error processing {txt_file.name}: {e}")
