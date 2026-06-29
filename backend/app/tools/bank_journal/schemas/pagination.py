from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页信封:items 为当前页数据,total 为过滤后总数。"""

    items: list[T]
    total: int
    limit: int
    offset: int
