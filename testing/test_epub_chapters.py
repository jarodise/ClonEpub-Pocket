import unittest
import os
import sys
import tempfile
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from clonepub.core import (
    extract_toc_map,
    extract_chapter_title,
    extract_text_from_soup,
    is_likely_chapter,
    extract_chapters,
    load_epub,
    create_index_file,
)


class TestEPUBChapters(unittest.TestCase):
    def test_extract_toc_map_flat_and_nested(self):
        """Test that extract_toc_map correctly extracts titles from flat and nested TOC structures."""
        class MockLink:
            def __init__(self, title, href):
                self.title = title
                self.href = href

        class MockSection:
            def __init__(self, title, href=""):
                self.title = title
                self.href = href

        mock_book = MagicMock()
        mock_book.toc = [
            MockLink("Cover Page", "cover.html"),
            MockLink("Introduction", "text/intro.html#start"),
            (
                MockSection("Part One", "text/part1.html"),
                [
                    MockLink("Chapter 1: The Beginning", "text/ch01.html#p1"),
                    MockLink("Chapter 2: The Journey", "text/ch02.html"),
                ],
            ),
            (
                "Part Two",
                [
                    MockLink("Chapter 3: The End", "text/ch03.html"),
                ],
            ),
        ]

        toc_map = extract_toc_map(mock_book)

        self.assertEqual(toc_map.get("cover.html"), "Cover Page")
        self.assertEqual(toc_map.get("text/intro.html"), "Introduction")
        self.assertEqual(toc_map.get("intro.html"), "Introduction")
        self.assertEqual(toc_map.get("text/part1.html"), "Part One")
        self.assertEqual(toc_map.get("part1.html"), "Part One")
        self.assertEqual(toc_map.get("text/ch01.html"), "Chapter 1: The Beginning")
        self.assertEqual(toc_map.get("ch01.html"), "Chapter 1: The Beginning")
        self.assertEqual(toc_map.get("ch02.html"), "Chapter 2: The Journey")
        self.assertEqual(toc_map.get("ch03.html"), "Chapter 3: The End")

    def test_extract_text_from_soup_div_layout_and_dropcaps(self):
        """Test that div-based paragraph layouts and drop caps are cleanly extracted."""
        html = """
        <html>
        <head><script>alert('bad');</script><style>.bad{}</style></head>
        <body>
            <div class="chapnum"><span><a href="contents.html#ch1" id="rch1">1</a></span></div>
            <div class="chaptitle">SEEING</div>
            <div class="chaptitle1">What Is Consciousness?</div>
            <div class="noindent"><span><span class="dropcap">W</span>hat exactly is consciousness? The oldest answer comes from India.<sup class="footnote">[1]</sup></span></div>
            <div class="indent">Long before Socrates and Plato's <i>Dialogues</i>, a great debate took place.<a href="#note1">[2]</a></div>
            <div class="container">
                <div class="inner-para">This is inside a nested block.</div>
            </div>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = extract_text_from_soup(soup)

        # Dropcap "W" and "hat" should be together as "What"
        self.assertIn("What exactly is consciousness? The oldest answer comes from India.", text)
        self.assertIn("Dialogues, a great debate took place.", text)
        self.assertIn("This is inside a nested block.", text)

        # Citations [1], [2] should be removed
        self.assertNotIn("[1]", text)
        self.assertNotIn("[2]", text)

        # Scripts and styles should be removed
        self.assertNotIn("alert", text)

    def test_extract_chapter_title_fallbacks(self):
        """Test chapter title extraction fallbacks (TOC -> headings -> classes -> filename)."""
        mock_item = MagicMock()
        mock_item.get_name.return_value = "OEBPS/ch05.xhtml"

        # 1. Matches TOC
        soup_empty = BeautifulSoup("<html><body><p>Text</p></body></html>", "lxml")
        title_from_toc = extract_chapter_title(
            mock_item, soup_empty, {"ch05.xhtml": "TOC Chapter 5"}, book_title="My Book"
        )
        self.assertEqual(title_from_toc, "TOC Chapter 5")

        # 2. In-document heading
        soup_heading = BeautifulSoup("<html><body><h1>Heading Chapter 5</h1></body></html>", "lxml")
        title_from_h = extract_chapter_title(
            mock_item, soup_heading, {}, book_title="My Book"
        )
        self.assertEqual(title_from_h, "Heading Chapter 5")

        # 3. Chapter title class
        soup_class = BeautifulSoup("<html><body><div class='chapter-title'>Class Title 5</div></body></html>", "lxml")
        title_from_class = extract_chapter_title(
            mock_item, soup_class, {}, book_title="My Book"
        )
        self.assertEqual(title_from_class, "Class Title 5")

        # 4. Filename fallback (ch05 -> Chapter 5)
        title_from_file = extract_chapter_title(
            mock_item, soup_empty, {}, book_title="My Book"
        )
        self.assertEqual(title_from_file, "Chapter 5")

    def test_is_likely_chapter_selection(self):
        """Test that content chapters are selected and auxiliary pages are unselected."""
        # Front/back matter should NOT be selected
        self.assertFalse(is_likely_chapter("Cover", "Short", "cover.html"))
        self.assertFalse(is_likely_chapter("Title Page", "x" * 500, "title.html"))
        self.assertFalse(is_likely_chapter("Copyright", "x" * 1500, "copyright.html"))
        self.assertFalse(is_likely_chapter("Contents", "x" * 800, "contents.html"))
        self.assertFalse(is_likely_chapter("Acknowledgments", "x" * 3000, "ack.html"))
        self.assertFalse(is_likely_chapter("Notes", "x" * 50000, "notes.html"))
        self.assertFalse(is_likely_chapter("Bibliography", "x" * 30000, "bib.html"))
        self.assertFalse(is_likely_chapter("Index", "x" * 40000, "index.html"))

        # Content chapters SHOULD be selected
        self.assertTrue(is_likely_chapter("Foreword", "x" * 8000, "foreword.html"))
        self.assertTrue(is_likely_chapter("Prologue: The Dalai Lama's Conjecture", "x" * 15000, "prologue.html"))
        self.assertTrue(is_likely_chapter("Introduction", "x" * 20000, "int.html"))
        self.assertTrue(is_likely_chapter("1. Seeing: What Is Consciousness?", "x" * 40000, "ch01.html"))
        self.assertTrue(is_likely_chapter("Chapter 10", "x" * 30000, "ch10.html"))

        # Single chapter book should always be selected
        self.assertTrue(is_likely_chapter("Index", "x" * 500, "index.html", total_chapters=1))

    def test_create_index_file_with_titles(self):
        """Test that create_index_file includes chapter titles in FFMETADATA1 output."""
        test_dir = tempfile.mkdtemp()
        try:
            # Create dummy chapter file
            dummy_file = Path(test_dir) / "dummy.m4a"
            dummy_file.write_text("fake audio")

            titles = ["Prologue", "1. Seeing"]
            # Mock probe_duration to return 10.0 seconds
            from unittest.mock import patch
            with patch("clonepub.core.probe_duration", return_value=10.0):
                index_path = create_index_file(
                    title="Test Book",
                    creator="Test Author",
                    chapter_mp3_files=[dummy_file, dummy_file],
                    output_folder=test_dir,
                    chapter_titles=titles,
                )

                content = Path(index_path).read_text(encoding="utf-8")
                self.assertIn("title=Prologue", content)
                self.assertIn("title=1. Seeing", content)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_user_epub_waking_dreaming_being(self):
        """End-to-end test on the user's EPUB book: Waking, Dreaming, Being."""
        epub_path = "/Users/jarodise/Downloads/Waking, Dreaming, Being (Evan Thompson) (z-library.sk, 1lib.sk, z-lib.sk).epub"
        if not os.path.exists(epub_path):
            self.skipTest(f"EPUB file not found at {epub_path}")

        data = load_epub(epub_path)
        self.assertEqual(data["title"], "Waking, Dreaming, Being")
        self.assertEqual(data["author"], "Evan Thompson")

        chapters = data["chapters"]
        # Must have extracted chapters (previously 0)
        self.assertGreater(len(chapters), 15)

        # Check that specific chapter titles from TOC are present
        chapter_names = [c["name"] for c in chapters]
        self.assertIn("Foreword", chapter_names)
        self.assertIn("Prologue: The Dalai Lama’s Conjecture", chapter_names)
        self.assertIn("Introduction", chapter_names)
        self.assertIn("1. Seeing: What Is Consciousness?", chapter_names)
        self.assertIn("10. Knowing: Is the Self an Illusion?", chapter_names)

        # Check selection states
        chapters_by_name = {c["name"]: c for c in chapters}
        self.assertTrue(chapters_by_name["Foreword"]["selected"])
        self.assertTrue(chapters_by_name["Prologue: The Dalai Lama’s Conjecture"]["selected"])
        self.assertTrue(chapters_by_name["Introduction"]["selected"])
        self.assertTrue(chapters_by_name["1. Seeing: What Is Consciousness?"]["selected"])
        self.assertTrue(chapters_by_name["10. Knowing: Is the Self an Illusion?"]["selected"])

        # Auxiliary chapters should NOT be selected
        if "Copyright" in chapters_by_name:
            self.assertFalse(chapters_by_name["Copyright"]["selected"])
        if "Contents" in chapters_by_name:
            self.assertFalse(chapters_by_name["Contents"]["selected"])
        if "Notes" in chapters_by_name:
            self.assertFalse(chapters_by_name["Notes"]["selected"])
        if "Bibliography" in chapters_by_name:
            self.assertFalse(chapters_by_name["Bibliography"]["selected"])
        if "Index" in chapters_by_name:
            self.assertFalse(chapters_by_name["Index"]["selected"])

    def test_quantum_psychology_split_chapter_stitching(self):
        """Test multi-file EPUB stitching and front/back matter exclusion on Quantum Psychology."""
        epub_path = Path(__file__).parent.parent / "Quantum Psychology How Brain Software Programs You and Your World (Robert Anton Wilson) (z-library.sk, 1lib.sk, z-lib.sk).epub"
        if not epub_path.exists():
            self.skipTest(f"EPUB file not found at {epub_path}")

        data = load_epub(str(epub_path))
        chapters = data["chapters"]
        chapter_names = [c["name"] for c in chapters]

        # 1. Orphan parts like "Part 7" or "Part 26" should NOT exist (they are stitched into their parents)
        self.assertNotIn("Part 7", chapter_names)
        self.assertNotIn("Part 26", chapter_names)
        self.assertNotIn("Part 41", chapter_names)

        # 2. Key narrative chapters should be present and complete
        chapters_by_name = {c["name"]: c for c in chapters}
        self.assertIn("Introduction", chapters_by_name)
        # Introduction includes both part0006 and part0007 (> 18000 chars)
        self.assertGreater(chapters_by_name["Introduction"]["length"], 15000)
        self.assertTrue(chapters_by_name["Introduction"]["selected"])

        # Chapter 13 includes both part0025 and part0026 (> 24000 chars)
        ch13_title = "13 - E and E-Prime"
        self.assertIn(ch13_title, chapters_by_name)
        self.assertGreater(chapters_by_name[ch13_title]["length"], 20000)
        self.assertTrue(chapters_by_name[ch13_title]["selected"])

        # 3. Front matter and Index should NOT be selected
        if "TABLE OF CONTENTS" in chapters_by_name:
            self.assertFalse(chapters_by_name["TABLE OF CONTENTS"]["selected"])
        if "Index" in chapters_by_name:
            self.assertFalse(chapters_by_name["Index"]["selected"])
        if "Index of Names" in chapters_by_name:
            self.assertFalse(chapters_by_name["Index of Names"]["selected"])

    def test_crystal_and_way_of_light_chapter_alignment(self):
        """Test that EPUBs with page-anchor TOCs do not cause off-by-one chapter title misattributions."""
        epub_name = "The Crystal and the Way of Light_ Sutra, Tantra, and -- Chogyal Namkhai Norbu & John Shane -- 1986 -- Snow Lion Publications, Incorporated -- isbn13 9781559391351 -- 95a5fb59393eccb8ea23800355be20c7 -- Anna’s Archive.epub"
        epub_path = Path(__file__).parent.parent / epub_name
        if not epub_path.exists():
            self.skipTest(f"EPUB file not found at {epub_path}")

        data = load_epub(str(epub_path))
        chapters = data["chapters"]
        chapters_by_name = {c["name"]: c for c in chapters}

        # 1. Front matter Contents should NOT be selected
        self.assertIn("Contents", chapters_by_name)
        self.assertFalse(chapters_by_name["Contents"]["selected"])

        # 2. Key narrative chapters must NOT have off-by-one titles:
        # Chapter 1 must be Chapter 1 (not Chapter 2)
        ch1_key = [k for k in chapters_by_name if "Chapter One" in k or "My Birth" in k]
        self.assertTrue(len(ch1_key) > 0, "Chapter One not found in chapters")
        ch1 = chapters_by_name[ch1_key[0]]
        self.assertIn("My Birth, Early Life, and Education", ch1["name"])
        self.assertIn("My Birth, Early Life", ch1["text"])
        self.assertTrue(ch1["selected"])

        # Chapter 2 must be Chapter 2 (not Chapter 3)
        ch2_key = [k for k in chapters_by_name if "Chapter Two" in k or "An Introductory Perspective" in k]
        self.assertTrue(len(ch2_key) > 0, "Chapter Two not found in chapters")
        ch2 = chapters_by_name[ch2_key[0]]
        self.assertIn("An Introductory Perspective", ch2["name"])
        self.assertIn("An Introductory Perspective", ch2["text"])
        self.assertTrue(ch2["selected"])

        # The Six Vajra Verses must be The Six Vajra Verses (not Chapter 1)
        self.assertIn("The Six Vajra Verses", chapters_by_name)
        v_ch = chapters_by_name["The Six Vajra Verses"]
        self.assertIn("Six Vajra", v_ch["text"])
        self.assertNotIn("Chapter One", v_ch["text"])

    def test_api_chapter_manual_controls(self):
        """Test ClonEpubAPI manual chapter controls (rename, merge with previous, delete)."""
        from clonepub.api import ClonEpubAPI

        api = ClonEpubAPI()
        api._chapters = [
            {"index": 0, "name": "Chapter 1", "text": "First chapter content.", "length": 21, "selected": True},
            {"index": 1, "name": "Chapter 2 Part A", "text": "Beginning of chapter 2.", "length": 23, "selected": True},
            {"index": 2, "name": "Chapter 2 Part B", "text": "Continuation of chapter 2.", "length": 26, "selected": True},
            {"index": 3, "name": "Back Matter", "text": "Index notes.", "length": 12, "selected": False},
        ]

        # 1. Rename
        rename_res = api.update_chapter_title(1, "Chapter 2: The Awakening")
        self.assertTrue(rename_res["success"])
        self.assertEqual(api._chapters[1]["name"], "Chapter 2: The Awakening")

        # 2. Merge with previous (merge index 2 into index 1)
        merge_res = api.merge_chapter_with_previous(2)
        self.assertTrue(merge_res["success"])
        self.assertEqual(len(api._chapters), 3)
        self.assertEqual(api._chapters[1]["name"], "Chapter 2: The Awakening")
        self.assertIn("Beginning of chapter 2.\n\nContinuation of chapter 2.", api._chapters[1]["text"])
        self.assertEqual(api._chapters[2]["name"], "Back Matter")
        self.assertEqual(api._chapters[2]["index"], 2)

        # 3. Delete chapter (delete index 2)
        delete_res = api.delete_chapter(2)
        self.assertTrue(delete_res["success"])
        self.assertEqual(len(api._chapters), 2)
        self.assertEqual(api._chapters[0]["name"], "Chapter 1")
        self.assertEqual(api._chapters[1]["name"], "Chapter 2: The Awakening")


if __name__ == "__main__":
    unittest.main()
