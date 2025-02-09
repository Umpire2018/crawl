from pathlib import Path
from models import DocPage, DocSection, DocBlock
from pydantic import BaseModel
from typing import List, Union
import asyncio
from loguru import logger


class DocSentenceProcessed(BaseModel):
    """Represents a sentence after processing references to a list of strings."""

    id: str
    text: str
    references: List[str]  # Converted from List[CitationData] to List[str]


class DocBlockProcessed(BaseModel):
    sentences: List[DocSentenceProcessed]


class DocSectionProcessed(BaseModel):
    id: str
    title: str
    content: List[
        Union["DocSectionProcessed", DocBlockProcessed]
    ]  # Allow nested structure


class DocPageProcessed(BaseModel):
    """Processed document where references are stored as List[str]."""

    title: str
    content: List[DocSectionProcessed]


async def transform_content(content) -> Union[DocSectionProcessed, DocBlockProcessed]:
    """
    Recursively process DocSection and DocBlock content, converting references to List[str].
    """
    if isinstance(content, DocSection):
        return DocSectionProcessed(
            id=content.id,
            title=content.title,
            content=[await transform_content(item) for item in content.content],
        )
    elif isinstance(content, DocBlock):
        return DocBlockProcessed(
            sentences=[
                DocSentenceProcessed(
                    id=sentence.id,
                    text=sentence.text,
                    references=[
                        ref.url for ref in sentence.references if ref.status_code == 200
                    ],
                )
                for sentence in content.sentences
            ]
        )



async def process_single_file(input_file: Path, output_dir: Path):
    """
    处理单个 JSON 文件，转换引用并保存到 `final/` 目录。
    """
    # 生成去掉 `_url_test` 后缀的最终文件名
    output_file = output_dir / (input_file.stem.replace("_url_test", "") + ".json")

    # **检查是否已处理，避免重复**
    if output_file.exists():
        logger.info(
            f"📌 Skipping {input_file.name} (already processed as {output_file.name})"
        )
        return

    # 读取 JSON 文件
    with open(input_file, "r", encoding="utf-8") as f:
        doc_json = f.read()

    # 解析为 DocPage
    doc_page = DocPage.model_validate_json(doc_json)

    # 转换内容结构
    processed_content = [
        await transform_content(section) for section in doc_page.content
    ]

    # 生成处理后的 DocPageProcessed 对象
    doc_page_processed = DocPageProcessed(
        title=doc_page.title, content=processed_content
    )

    # 保存转换后的 JSON 文件
    with open(output_file, "w", encoding="utf-8") as fw:
        fw.write(doc_page_processed.model_dump_json(indent=2))

    logger.success(f"✅ Processed and saved: {output_file}")


async def process_json_files(
    input_dir: Path = Path("processed"), output_dir: Path = Path("final")
):
    """
    处理所有 `url_test.json` 结尾的 JSON 文件，并保存到 `final/` 目录，去掉 `_url_test` 后缀。
    """
    output_dir.mkdir(parents=True, exist_ok=True)  # 确保输出目录存在

    # 只选取文件名包含 `_url_test.json` 的 JSON 文件
    input_files = [file for file in input_dir.glob("*.json") if "url_test" in file.stem]

    if not input_files:
        logger.warning("❌ No `url_test.json` files found in input directory.")
        return

    tasks = [process_single_file(input_file, output_dir) for input_file in input_files]

    await asyncio.gather(*tasks)  # 并发处理文件

    logger.info("✅ Finished processing all `url_test.json` files.")


# Example execution
if __name__ == "__main__":
    asyncio.run(process_json_files())
