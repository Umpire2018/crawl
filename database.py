# database.py
import re

from loguru import logger
from sqlmodel import Session, SQLModel, create_engine, delete, select

from models import NewsLink

DATABASE_URL = "sqlite:///news_links.db"
engine = create_engine(DATABASE_URL)


def create_db():
    """创建数据库表"""
    SQLModel.metadata.create_all(engine)
    logger.info("✅ Database initialized.")


def year_exists(year: str) -> bool:
    with Session(engine) as session:
        existing_entry = session.exec(
            select(NewsLink).where(NewsLink.year == year)
        ).first()
        return existing_entry is not None


def save_to_db(links, year):
    """将链接中包含四位数年份的存入数据库，并检查年份范围"""
    with Session(engine) as session:
        new_links = 0
        year_pattern = re.compile(r"\d{4}")

        for link in links:
            match = year_pattern.search(link)  # Find only the first match
            if match:
                found_year = match.group()

                if found_year == str(year):
                    try:
                        session.add(NewsLink(url=link, year=year))
                        session.commit()  # Try inserting directly
                        new_links += 1
                    except Exception:
                        session.rollback()  # Rollback if unique constraint fails
        session.commit()

    logger.info(
        f"✅ Saved {new_links} new links for {year}. Total links processed: {len(links)}"
    )


def get_first_n_links(n: int = 1000):
    """返回数据库中前n条新闻链接，默认返回前 1000 条"""
    with Session(engine) as session:
        results = session.exec(select(NewsLink.url).limit(n)).all()
    logger.info(f"📌 Retrieved {len(results)} links from database.")
    return results


def delete_link(title: str):
    """从数据库中删除指定的 Wikipedia 链接"""
    with Session(engine) as session:
        stmt = delete(NewsLink).where(NewsLink.url.contains(title.replace(" ", "_")))
        result = session.exec(stmt)
        session.commit()

        if result.rowcount > 0:
            logger.info(f"🗑 Deleted link '{title}' from database.")
        else:
            logger.warning(f"⚠️ No link found for '{title}' in database.")
