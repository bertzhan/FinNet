"""
Unit tests for HTML processing: encoding preservation and image path rewriting.

Test-Driven Development approach:
1. Write tests that define expected behavior
2. Tests will initially fail
3. Implement minimal code to pass tests
"""
import pytest
from pathlib import Path
from bs4 import BeautifulSoup


class TestHTMLEncodingPreservation:
    """Test that HTML processing preserves original encoding declarations."""

    def test_ascii_declaration_preserved(self):
        """ASCII-declared content should remain ASCII after processing."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html>
<head><title>Test Document</title></head>
<body>
<p>Officer's Certificate of the Registrant</p>
<img src="https://www.sec.gov/Archives/edgar/data/123/image.gif"/>
</body>
</html>"""

        # Import the function we'll create
        from utils.html_processor import process_html_preserve_encoding

        result = process_html_preserve_encoding(original_html, img_replacements={})

        # Verify ASCII declaration is preserved
        assert b"encoding='ASCII'" in result

        # Verify no UTF-8 multi-byte characters were introduced
        # UTF-8 right quote: \xe2\x80\x99
        # UTF-8 em-dash: \xe2\x80\x94
        assert b'\xe2\x80\x99' not in result  # right single quote
        assert b'\xe2\x80\x94' not in result  # em-dash
        assert b'\xe2\x80\x9c' not in result  # left double quote
        assert b'\xe2\x80\x9d' not in result  # right double quote

        # Verify apostrophe stays as ASCII apostrophe
        assert b"Officer's" in result or b"Officer&#39;s" in result

    def test_utf8_declaration_preserved(self):
        """UTF-8 declared content should remain UTF-8 after processing."""
        original_html = b"""<?xml version='1.0' encoding='UTF-8'?>
<html>
<body>
<p>Test with UTF-8 chars: \xe2\x80\x93</p>
<img src="/edgar/image.png"/>
</body>
</html>"""

        from utils.html_processor import process_html_preserve_encoding

        result = process_html_preserve_encoding(original_html, img_replacements={})

        # Verify UTF-8 declaration is preserved
        assert b"encoding='UTF-8'" in result

        # Verify UTF-8 content is preserved
        assert b'\xe2\x80\x93' in result

    def test_no_encoding_declaration_handles_utf8(self):
        """HTML without encoding declaration should handle UTF-8 gracefully."""
        original_html = b"""<html>
<body>
<p>Modern HTML with UTF-8: \xe2\x80\x94</p>
</body>
</html>"""

        from utils.html_processor import process_html_preserve_encoding

        result = process_html_preserve_encoding(original_html, img_replacements={})

        # Should not crash
        assert result is not None
        # UTF-8 content should be preserved
        assert b'\xe2\x80\x94' in result

    def test_mixed_quotes_preserved(self):
        """Test that various quote styles are preserved without normalization."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<p>Test "double quotes" and 'single quotes'</p>
<p>Apostrophes in words: don't, can't, won't</p>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        result = process_html_preserve_encoding(original_html, img_replacements={})

        # Verify ASCII quotes are NOT converted to UTF-8 smart quotes
        assert b'\xe2\x80\x99' not in result  # no UTF-8 right single quote
        assert b'\xe2\x80\x9c' not in result  # no UTF-8 left double quote
        assert b'\xe2\x80\x9d' not in result  # no UTF-8 right double quote


class TestImagePathRewriting:
    """Test that image paths are correctly rewritten to relative local paths."""

    def test_absolute_sec_url_rewritten_to_relative(self):
        """SEC absolute URLs should be rewritten to relative local paths."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<img src="https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/image001.gif"/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        img_replacements = {
            "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/image001.gif": "./AAPL_2025_FY_31-10-2025_image-001.gif"
        }

        result = process_html_preserve_encoding(original_html, img_replacements)

        # Parse result to check img src
        soup = BeautifulSoup(result, 'html.parser')
        img_tag = soup.find('img')

        assert img_tag is not None
        assert img_tag.get('src') == "./AAPL_2025_FY_31-10-2025_image-001.gif"

    def test_relative_sec_url_rewritten_to_local(self):
        """Relative SEC URLs should be rewritten to relative local paths."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<img src="/Archives/edgar/data/320193/img.png"/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        img_replacements = {
            "/Archives/edgar/data/320193/img.png": "./AAPL_2025_FY_31-10-2025_image-002.png"
        }

        result = process_html_preserve_encoding(original_html, img_replacements)

        soup = BeautifulSoup(result, 'html.parser')
        img_tag = soup.find('img')

        assert img_tag.get('src') == "./AAPL_2025_FY_31-10-2025_image-002.png"

    def test_multiple_images_rewritten(self):
        """Multiple image tags should all be rewritten correctly."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<img src="https://sec.gov/img1.jpg"/>
<img src="https://sec.gov/img2.png"/>
<img src="/edgar/img3.gif"/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        img_replacements = {
            "https://sec.gov/img1.jpg": "./local_image-001.jpg",
            "https://sec.gov/img2.png": "./local_image-002.png",
            "/edgar/img3.gif": "./local_image-003.gif"
        }

        result = process_html_preserve_encoding(original_html, img_replacements)

        soup = BeautifulSoup(result, 'html.parser')
        img_tags = soup.find_all('img')

        assert len(img_tags) == 3
        assert img_tags[0].get('src') == "./local_image-001.jpg"
        assert img_tags[1].get('src') == "./local_image-002.png"
        assert img_tags[2].get('src') == "./local_image-003.gif"

    def test_images_not_in_mapping_unchanged(self):
        """Images not in replacement mapping should remain unchanged."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<img src="https://external.com/logo.png"/>
<img src="https://sec.gov/known.jpg"/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        img_replacements = {
            "https://sec.gov/known.jpg": "./local_known.jpg"
        }

        result = process_html_preserve_encoding(original_html, img_replacements)

        soup = BeautifulSoup(result, 'html.parser')
        img_tags = soup.find_all('img')

        # First image should be unchanged (not in mapping)
        assert img_tags[0].get('src') == "https://external.com/logo.png"
        # Second image should be rewritten
        assert img_tags[1].get('src') == "./local_known.jpg"


class TestIntegration:
    """Integration tests combining encoding preservation and image rewriting."""

    def test_real_world_aapl_scenario(self):
        """Test realistic AAPL 10-K scenario with ASCII encoding and multiple images."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>FORM 10-K</title>
</head>
<body>
<p style="margin-top:12pt; margin-bottom:0pt; font-size:10pt; font-family:Times New Roman">
Officer's Certificate of the Registrant, dated as of February 8, 2021
</p>
<p>The company's revenue increased 5% year-over-year.</p>
<table>
<tr><td><img src="https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/g1.gif" style="width:100%"/></td></tr>
<tr><td><img src="/Archives/edgar/data/320193/000032019325000001/g2.gif"/></td></tr>
</table>
</body>
</html>"""

        from utils.html_processor import process_html_preserve_encoding

        img_replacements = {
            "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/g1.gif": "./AAPL_2025_FY_31-10-2025_image-001.gif",
            "/Archives/edgar/data/320193/000032019325000001/g2.gif": "./AAPL_2025_FY_31-10-2025_image-002.gif"
        }

        result = process_html_preserve_encoding(original_html, img_replacements)

        # Verify encoding declaration preserved
        assert b"encoding='ASCII'" in result

        # Verify no UTF-8 mojibake introduced
        assert b'\xe2\x80\x99' not in result  # no smart quotes
        assert b'\xe2\x80\x94' not in result  # no em-dash

        # Verify apostrophes preserved (not converted to smart quotes)
        assert b"Officer's" in result or b"Officer&#39;s" in result

        # Verify images rewritten
        soup = BeautifulSoup(result, 'html.parser')
        img_tags = soup.find_all('img')

        assert len(img_tags) == 2
        assert img_tags[0].get('src') == "./AAPL_2025_FY_31-10-2025_image-001.gif"
        assert img_tags[1].get('src') == "./AAPL_2025_FY_31-10-2025_image-002.gif"

        # Verify other attributes preserved
        assert img_tags[0].get('style') == "width:100%"

    def test_file_size_minimal_increase(self):
        """Test that file size increase is minimal (only due to path changes)."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<p>Content with lots of text that should not change size</p>
<img src="https://www.sec.gov/very/long/path/to/image.gif"/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        img_replacements = {
            "https://www.sec.gov/very/long/path/to/image.gif": "./short.gif"
        }

        result = process_html_preserve_encoding(original_html, img_replacements)

        # File should be SMALLER (shorter path)
        assert len(result) < len(original_html)

        # But if we use longer local path
        img_replacements_long = {
            "https://www.sec.gov/very/long/path/to/image.gif": "./COMPANY_2025_FY_31-10-2025_image-001.gif"
        }

        result_long = process_html_preserve_encoding(original_html, img_replacements_long)

        # File size increase should be roughly = (new path length - old path length)
        size_diff = len(result_long) - len(original_html)
        path_diff = len(b"./COMPANY_2025_FY_31-10-2025_image-001.gif") - len(b"https://www.sec.gov/very/long/path/to/image.gif")

        # Allow some tolerance for HTML formatting differences
        assert abs(size_diff - path_diff) < 100, f"Size increase {size_diff} should be close to path diff {path_diff}"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_html_handled_gracefully(self):
        """Malformed HTML should be handled without crashing."""
        malformed_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<p>Unclosed tag
<img src="test.gif"
</body>"""

        from utils.html_processor import process_html_preserve_encoding

        # Should not raise exception
        result = process_html_preserve_encoding(malformed_html, img_replacements={})
        assert result is not None

    def test_empty_img_src_ignored(self):
        """Image tags with empty src should be ignored."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<img src=""/>
<img/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        result = process_html_preserve_encoding(original_html, img_replacements={})
        assert result is not None

    def test_special_html_entities_preserved(self):
        """HTML entities like &lt; &gt; &amp; should be preserved."""
        original_html = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<p>Test entities: &lt;tag&gt; &amp; more</p>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding

        result = process_html_preserve_encoding(original_html, img_replacements={})

        # Basic entities should be preserved
        result_str = result.decode('ascii', errors='replace')
        # These entities are essential for HTML structure
        assert '&lt;' in result_str
        assert '&gt;' in result_str
        assert '&amp;' in result_str
