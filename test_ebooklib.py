from ebooklib import epub
item = epub.EpubItem(uid="test")
print(f"ID: {item.id}")
print(f"UID: {getattr(item, 'uid', 'MISSING')}")
print(f"Attributes: {dir(item)}")