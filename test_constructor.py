from ebooklib import epub
try:
    print("Testing EpubItem(uid='test')")
    item = epub.EpubItem(uid="test")
    print(f"Success! ID: {item.id}")
except Exception as e:
    print(f"Error with uid=: {e}")

try:
    print("\nTesting EpubItem('test2')")
    item2 = epub.EpubItem("test2")
    print(f"Success! ID: {item2.id}")
except Exception as e:
    print(f"Error with positional: {e}")