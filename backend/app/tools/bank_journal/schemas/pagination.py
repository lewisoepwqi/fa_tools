from pydantic import BaseModel


class Page[T](BaseModel):
    """分页信封:items 为当前页数据,total 为过滤后总数。"""

    items: list[T]
    total: int
    limit: int
    offset: int
