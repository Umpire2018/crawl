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
    def extract_title(x: str) -> str:
        """
        从文本中提取形如 "|title=xxx" 的标题，
        若无法提取则返回 "Untitled"。
        """
        t = re.search(r"\|title\s*=\s*(.*?)\n", x)
        return t.group(1).strip() if t else "Untitled"

    @staticmethod
    def replace_info(x: str) -> str:
        """
        将从文件起始行到第二个独立 '}}' 行之间的内容替换为 "==序言=="。
        主要用于去除特定的 infobox 块或其他元信息。
        """
        fs = list(re.finditer(r"^\}\}\s*$", x, re.MULTILINE))
        if len(fs) >= 2:
            x = "==序言==\n" + x[fs[1].end() :]
        return x

    @staticmethod
    def parse_file(path: str) -> str:
        """
        读取指定文件，提取标题，并解析章节和文本块，最终返回 JSON 串。
        """
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()

        doc_title = Rewriter.extract_title(data)
        data = Rewriter.replace_info(data)

        # 匹配顶级章节行，如 "== XXX =="
        pat = re.compile(r"^\s*==\s*([^=]+?)\s*==\s*$", re.MULTILINE)
        top = list(pat.finditer(data))
        sections = []

        for i, heading in enumerate(top):
            heading_text = heading.group(1).strip()
            start = heading.end()
            end = top[i + 1].start() if (i + 1 < len(top)) else len(data)
            sub = data[start:end].strip()

            # 解析次级章节
            parsed = Rewriter.section_parse(sub, str(i + 1), 2)
            sections.append(
                DocSection(id=str(i + 1), title=heading_text, content=parsed)
            )

        doc = DocPage(title=doc_title, content=sections)

        # 以 JSON 格式导出
        return doc.model_dump_json(indent=2)

    @staticmethod
    def process_folder(
        input_dir: Path = Path("original"), output_dir: Path = Path("processed")
    ):
        """
        处理 input_dir 目录下的所有 .txt 文件，并将解析结果保存到 output_dir 目录。

        :param input_dir: 输入文件夹路径，包含待处理的 .txt 文件
        :param output_dir: 输出文件夹路径，解析后的 JSON 文件将保存在这里
        """

        output_dir.mkdir(parents=True, exist_ok=True)  # 确保输出目录存在

        for txt_file in input_dir.glob("*.txt"):
            try:
                # 解析文件
                parsed_json = Rewriter.parse_file(str(txt_file))

                # 生成输出文件路径（更改扩展名为 .json）
                output_file = output_dir / (txt_file.stem + ".json")

                # 保存 JSON
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(parsed_json)

                logger.success(f"Saved parsed file: {output_file}")

            except Exception as e:
                logger.error(f"Error processing {txt_file.name}: {e}")
