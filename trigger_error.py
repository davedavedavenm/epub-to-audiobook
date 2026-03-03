from ebooklib import epub
try:
    item = epub.EpubItem(uid="test")
    print(f"ID via attribute: {item.id}")
    print(f"ID via get_id(): {item.get_id()}")
    # Trigger the error
    print(f"UID: {item.uid}")
except Exception as e:
    print(f"Error caught as expected: {e}")