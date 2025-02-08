from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional


class CitationData(BaseModel):
    # Original text
    text: Optional[str] = None
    # Extracted URL from '|url=' field; if extraction fails, remains None
    url: Optional[str] = None
    # Whether the URL is accessible; if not checked, remains None
    accessible: Optional[bool] = None
    # Type extracted from '{{Cite ...' (e.g., 'news' or 'web'); if extraction fails, remains None
    type: Optional[str] = None


class DocSentence(BaseModel):
    """
    表示文档中的一个句子（含引用信息）。
    """

    id: str
    text: str
    references: List[CitationData]


class DocBlock(BaseModel):
    """
    表示一个文本块，由若干句子（DocSentence）组成。
    """

    sentences: List[DocSentence]


class DocSection(BaseModel):
    """
    表示一个章节，可嵌套子章节（DocSection）或文本块（DocBlock）。
    """

    id: str
    title: str
    content: List[DocSection | DocBlock]


class DocPage(BaseModel):
    """
    表示文档的顶层页面，包含标题和若干章节（DocSection）。
    """

    title: str
    content: List[DocSection]


# 处理 DocSection 的自引用
DocSection.model_rebuild()

from sqlmodel import SQLModel, Field


class NewsLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    month: str  # 格式："YYYY_Month"
