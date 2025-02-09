# database.py
from sqlmodel import SQLModel, Session, create_engine, select, delete
from models import NewsLink
from loguru import logger
import re


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
    """将链接中包含四位数年份的存入数据库"""
    with Session(engine) as session:
        new_links = 0
        year_pattern = re.compile(r"\d{4}")

        for link in links:
            if year_pattern.search(link):  # 仅处理包含年份的链接
                existing_link = session.exec(
                    select(NewsLink).where(NewsLink.url == link)
                ).first()
                if not existing_link:
                    session.add(NewsLink(url=link, year=year))
                    new_links += 1

        session.commit()

    logger.info(
        f"✅ Saved {new_links} new links containing a year for {year}. Total links processed: {len(links)}"
    )


def get_first_n_links(year: str, n: int = 10):
    with Session(engine) as session:
        results = session.exec(
            select(NewsLink.url).where(NewsLink.year == year).limit(n)
        ).all()
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
