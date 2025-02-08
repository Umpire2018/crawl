# database.py
from sqlmodel import SQLModel, Session, create_engine, select
from models import NewsLink
from loguru import logger

DATABASE_URL = "sqlite:///news_links.db"
engine = create_engine(DATABASE_URL)


def create_db():
    """创建数据库表"""
    SQLModel.metadata.create_all(engine)
    logger.info("✅ Database initialized.")


def month_exists(month: str) -> bool:
    """检查数据库中是否已存储该月份的数据"""
    with Session(engine) as session:
        existing_entry = session.exec(
            select(NewsLink).where(NewsLink.month == month)
        ).first()
        return existing_entry is not None


def save_to_db(links, month):
    """将链接存入数据库"""
    with Session(engine) as session:
        new_links = 0
        for link in links:
            # 避免重复插入
            existing_link = session.exec(
                select(NewsLink).where(NewsLink.url == link)
            ).first()
            if not existing_link:
                session.add(NewsLink(url=link, month=month))
                new_links += 1
        session.commit()

    logger.info(
        f"✅ Saved {new_links} new links for {month}. Total links processed: {len(links)}"
    )

def get_first_n_links(month: str, n: int = 10):
    """查询数据库中指定月份的前 N 条链接"""
    with Session(engine) as session:
        results = session.exec(
            select(NewsLink.url).where(NewsLink.month == month).limit(n)
        ).all()
    logger.info(f"📌 Retrieved {len(results)} links from database.")
    return results