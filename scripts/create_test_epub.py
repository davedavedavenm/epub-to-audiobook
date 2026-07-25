from ebooklib import epub

book = epub.EpubBook()
book.set_identifier("nlptest001")
book.set_title("NLP Pacing Test")
book.set_language("en")
book.add_author("Gemini")

# Chapter 1
c1 = epub.EpubHtml(title="Introduction", file_name="chap_1.xhtml", lang="en")
c1.content = "<html><body><h1>Introduction</h1><p>This is a test of the new NLP pacing system. It should handle sentences like this one very naturally. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.</p></body></html>"
book.add_item(c1)

# Chapter 2
c2 = epub.EpubHtml(title="Conclusion", file_name="chap_2.xhtml", lang="en")
c2.content = "<html><body><h1>Conclusion</h1><p>If you can hear this, the proxy is successfully routing Edge TTS. Check the logs for duration data.</p></body></html>"
book.add_item(c2)

book.toc = (epub.Link("chap_1.xhtml", "Introduction", "intro"),
            epub.Link("chap_2.xhtml", "Conclusion", "outro"))

book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

book.spine = ["nav", c1, c2]
epub.write_epub("/data/uploads/nlp_test.epub", book)
