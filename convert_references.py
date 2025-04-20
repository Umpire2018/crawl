import json
import re
from pathlib import Path
from typing import List, Union

from loguru import logger
from pydantic import BaseModel

from models import DocBlock, DocPage, DocSection


class DocSentenceProcessed(BaseModel):
    """Represents a sentence after processing references to a list of strings."""

    id: str
    text: str
    references: List[str]


class DocBlockProcessed(BaseModel):
    sentences: List[DocSentenceProcessed]


class DocSectionProcessed(BaseModel):
    id: str
    title: str
    content: List[Union["DocSectionProcessed", DocBlockProcessed]]


class DocPageProcessed(BaseModel):
    """Processed document where references are stored as List[str]."""

    title: str
    content: List[DocSectionProcessed]


def transform_content(content) -> Union[DocSectionProcessed, DocBlockProcessed, None]:
    """
    Recursively process DocSection and DocBlock content, converting references to List[str].
    Removes empty sentences, blocks, and sections, while ensuring IDs are sequentially reordered.
    """
    if isinstance(content, DocSection):
        processed_content = [transform_content(item) for item in content.content]
        processed_content = [item for item in processed_content if item is not None]

        if not processed_content:
            return None  # Remove empty sections

        return DocSectionProcessed(
            id=content.id,
            title=content.title,
            content=processed_content,
        )

    elif isinstance(content, DocBlock):
        processed_sentences = [
            DocSentenceProcessed(
                id=sentence.id,
                # use DOTALL so that '.' matches new line
                text=re.sub(
                    r"<ref[^>]*?/>|\{\{clear\}\}|\{\{Main.*?\|.*?\}\}",
                    "",
                    sentence.text,
                    flags=re.DOTALL,
                ).strip(),
                references=[
                    ref.url for ref in sentence.references if ref.status_code == 200
                ],
            )
            for sentence in content.sentences
            if any(ref.status_code == 200 for ref in sentence.references)
        ]

        if not processed_sentences:
            return None  # Remove empty blocks

        return DocBlockProcessed(sentences=processed_sentences)


def reorder_section_ids(page: DocPageProcessed):
    """
    Reorders section and sentence IDs to ensure proper sequential numbering.
    """
    for section_index, section in enumerate(page.content, start=1):
        section.id = f"{section_index}"  # ✅ Assign sequential section IDs
        reorder_subsection_ids(section, parent_id=section.id)


def reorder_subsection_ids(section: DocSectionProcessed, parent_id: str):
    """
    Recursively reorders IDs for nested sections.
    """
    for index, sub in enumerate(section.content, start=1):
        if isinstance(sub, DocSectionProcessed):  # ✅ Only sections have IDs
            sub.id = f"{parent_id}.{index}"
            reorder_subsection_ids(sub, parent_id=sub.id)
        elif isinstance(sub, DocBlockProcessed):  # ❌ No ID for DocBlockProcessed
            for sentence_index, sentence in enumerate(sub.sentences, start=1):
                sentence.id = f"{parent_id}.s{sentence_index}"  # ✅ Reorder sentences


def transform_page(page: DocPage) -> DocPageProcessed:
    """Processes an entire document page, applying transformations, removals, and ID reordering."""
    processed_sections = [transform_content(section) for section in page.content]
    processed_sections = [
        section for section in processed_sections if section is not None
    ]

    processed_page = DocPageProcessed(title=page.title, content=processed_sections)

    # Reorder section and sentence IDs
    reorder_section_ids(processed_page)

    return processed_page


def transform_json_files(
    source_dir: Path = Path("processed"), target_dir: Path = Path("final")
):
    target_dir.mkdir(parents=True, exist_ok=True)  # Ensure target directory exists

    json_files = list(source_dir.glob("*.json"))

    if not json_files:
        logger.warning("❌ No JSON files found in source directory.")
        return

    for file_path in json_files:
        output_path = target_dir / file_path.name

        if output_path.exists():
            continue

        # Read JSON file
        with open(file_path, "r", encoding="utf-8") as input_file:
            page_data = json.load(input_file)

        # Parse JSON into DocPage model
        doc_page = DocPage.model_validate(page_data)

        # Transform page content
        transformed_page = transform_page(doc_page)

        # Save transformed JSON
        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump(
                transformed_page.model_dump(), output_file, indent=2, ensure_ascii=False
            )

    logger.info("✅ Finished transforming all JSON files.")


# Example execution
if __name__ == "__main__":
    transform_json_files()
