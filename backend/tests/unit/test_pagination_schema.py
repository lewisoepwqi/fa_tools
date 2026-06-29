from pydantic import BaseModel

from app.tools.bank_journal.schemas.pagination import Page


class _Item(BaseModel):
    name: str


def test_page_envelope_serializes():
    page = Page[_Item](items=[_Item(name="a")], total=5, limit=2, offset=0)
    dumped = page.model_dump()
    assert dumped == {"items": [{"name": "a"}], "total": 5, "limit": 2, "offset": 0}


def test_page_empty():
    page = Page[_Item](items=[], total=0, limit=100, offset=0)
    assert page.items == [] and page.total == 0
