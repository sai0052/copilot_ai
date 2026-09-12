from fastapi import APIRouter, HTTPException

from app.models.item import Item

router = APIRouter(prefix="/items", tags=["items"])

_ITEMS = {
    1: Item(id=1, name="Notebook", price=4.5),
    2: Item(id=2, name="Pen", price=1.25),
}


@router.get("", response_model=list[Item])
def list_items() -> list[Item]:
    return list(_ITEMS.values())


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    item = _ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
