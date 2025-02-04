from sqlmodel import SQLModel, Session, select, Field
from sqlalchemy import create_engine
import re


# 定义数据模型
class Articles(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    title: str
    link: str


def extract_max_year(title: str) -> int:
    """
    查找标题中所有 4 位数的年份，返回其中的最大值；
    如果没有找到年份，则返回 -1。
    """
    matches = re.findall(r"(\d{4})", title)
    if not matches:
        return -1
    # 转换为 int 后，返回最大值
    years = [int(y) for y in matches]
    return max(years)


def get_filtered_links(db_url: str):
    """
    从数据库中读取 title 升序的前 20 条记录，
    筛选出标题中有年份 >= 2018 的链接。
    """
    engine = create_engine(db_url)
    with Session(engine) as session:
        # 按 title 升序，取前20条
        statement = select(Articles).order_by(Articles.title).limit(20)
        articles = session.exec(statement).all()

        # 过滤：只保留最大年份 >= 2018
        filtered_links = []
        for article in articles:
            max_year = extract_max_year(article.title)
            if max_year >= 2022:
                filtered_links.append(article.link)

    return filtered_links


# 示例调用
if __name__ == "__main__":
    db_url = "sqlite:///articles.db"
    links = get_filtered_links(db_url)
    print(links)
