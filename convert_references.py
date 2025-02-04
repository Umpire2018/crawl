from pathlib import Path
from models import DocPage, DocSection, DocBlock
from pydantic import BaseModel
from typing import List, Union
import asyncio

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
    content: List[Union["DocSectionProcessed", DocBlockProcessed]]  # Allow nested structure

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
            content=[await transform_content(item) for item in content.content]
        )
    elif isinstance(content, DocBlock):
        return DocBlockProcessed(
            sentences=[
                DocSentenceProcessed(
                    id=sentence.id,
                    text=sentence.text,
                    references=[ref.url for ref in sentence.references if ref.accessible]
                ) for sentence in content.sentences
            ]
        )

async def process_single_file(input_file: Path, output_dir: Path):
    """
    Process a single JSON file, converting references and saving the output.
    """
    output_path = output_dir / input_file.name  # Generate output file path

    # Read the JSON file
    with open(input_file, "r", encoding="utf-8") as f:
        doc_json = f.read()

    # Parse as DocPage
    doc_page = DocPage.model_validate_json(doc_json)

    # Convert content structure
    processed_content = [await transform_content(section) for section in doc_page.content]

    # Create processed DocPage object
    doc_page_processed = DocPageProcessed(title=doc_page.title, content=processed_content)

    # Save the transformed JSON
    with open(output_path, "w", encoding="utf-8") as fw:
        fw.write(doc_page_processed.model_dump_json(indent=2))

    print(f"Processed and saved: {output_path}")

async def process_json_files(input_dir: Path = Path("processed"), output_dir: Path = Path("final")):
    """
    Process all JSON files in the input directory and save them in the output directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists

    input_files = list(input_dir.glob("*.json"))  # Get all .json files
    tasks = [process_single_file(input_file, output_dir) for input_file in input_files]

    await asyncio.gather(*tasks)  # Process files concurrently

# Example execution
if __name__ == "__main__":
    asyncio.run(process_json_files())
