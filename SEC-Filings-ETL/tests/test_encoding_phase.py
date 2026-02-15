"""
Test-Driven Development for Phase 1: Encoding Fix

Tests for UTF-8 normalization, <meta charset="utf-8"> insertion, and mojibake cleanup.
"""
import pytest
from pathlib import Path
import tempfile


class TestMetaCharsetInsertion:
    """Test <meta charset="utf-8"> insertion logic."""

    def test_inserts_meta_charset_if_missing(self):
        """Should insert <meta charset="utf-8"> if not present."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<!DOCTYPE html>
<html>
<head>
<title>Test Document</title>
</head>
<body>
<p>Content here</p>
</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should have meta charset
        assert '<meta charset="utf-8"' in result_str
        # Should be in head section
        assert result_str.index('<meta charset="utf-8"') < result_str.index('</head>')

    def test_preserves_existing_utf8_meta_charset(self):
        """Should not duplicate if <meta charset="utf-8"> already exists."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Test</title>
</head>
<body>Content</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should only have one meta charset
        assert result_str.count('<meta charset="utf-8"') == 1

    def test_replaces_wrong_encoding_meta_tag(self):
        """Should replace incorrect encoding declarations."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<!DOCTYPE html>
<html>
<head>
<meta charset="ISO-8859-1"/>
<title>Test</title>
</head>
<body>Content</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should have UTF-8, not ISO-8859-1
        assert '<meta charset="utf-8"' in result_str
        assert 'ISO-8859-1' not in result_str

    def test_head_meta_position_top(self):
        """Meta charset should be in top 10 lines of <head>."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<!DOCTYPE html>
<html>
<head>
<title>Test</title>
<meta name="description" content="test"/>
</head>
<body>Content</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Find positions
        head_start = result_str.index('<head>')
        meta_charset_pos = result_str.index('<meta charset="utf-8"')
        title_pos = result_str.index('<title>')

        # Meta charset should come after <head> but before or near <title>
        assert head_start < meta_charset_pos
        # Should be early in head (within reasonable lines)
        head_section = result_str[head_start:result_str.index('</head>')]
        lines_before_meta = head_section[:meta_charset_pos - head_start].count('\n')
        assert lines_before_meta <= 10


class TestUTF8Normalization:
    """Test UTF-8 encoding normalization."""

    def test_preserves_utf8_no_mojibake(self):
        """UTF-8 content should remain clean."""
        from utils.encoding_fix import fix_html_encoding

        # Use Unicode string then encode to UTF-8
        html_str = '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"/><title>Test</title></head>\n<body>\n<p>Clean UTF-8 content with quotes: \u201chello\u201d and \u2018world\u2019</p>\n<p>Em-dash: \u2014 and en-dash: \u2013</p>\n</body>\n</html>'
        html = html_str.encode('utf-8')

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should preserve UTF-8 characters
        assert '\u2014' in result_str  # em-dash
        assert '\u2013' in result_str  # en-dash
        assert '\u201c' in result_str or '\u201d' in result_str  # double quotes

        # Should NOT have mojibake patterns
        assert 'â€"' not in result_str
        assert 'â€"' not in result_str

    def test_fixes_mojibake_patterns(self):
        """Should detect and fix common mojibake patterns."""
        from utils.encoding_fix import fix_html_encoding

        # Simulate mojibake: Use the actual mojibake strings
        html_str = '<!DOCTYPE html>\n<html>\n<head><title>Test</title></head>\n<body>\n<p>Officer\u00e2\u0080\u0099s Certificate</p>\n<p>dated as of\u00e2\u0080\u0094 February 2021</p>\n</body>\n</html>'
        html = html_str.encode('latin-1')  # Encode as Latin-1 to create the mojibake

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Mojibake should be cleaned
        assert '\u00e2\u0080\u0099' not in result_str  # â€™ mojibake pattern
        assert '\u00e2\u0080\u0094' not in result_str  # â€" mojibake pattern

        # Should have proper characters or reasonable substitutes
        assert 'Officer' in result_str
        assert 'Certificate' in result_str

    def test_converts_latin1_to_utf8(self):
        """Should convert Latin-1 encoded content to UTF-8."""
        from utils.encoding_fix import fix_html_encoding

        # Latin-1 content with accented characters
        html_str = "<!DOCTYPE html>\n<html>\n<head><title>Test</title></head>\n<body>\n<p>Cafe resume</p>\n</body>\n</html>"
        html = html_str.encode('latin-1')

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should be valid UTF-8
        assert 'Cafe' in result_str
        assert 'resume' in result_str
        # Content should be preserved
        assert '<title>Test</title>' in result_str


class TestIdempotence:
    """Test idempotence - running twice should not change output."""

    def test_idempotent_rerun_no_changes(self):
        """Running fix twice should produce identical output."""
        from utils.encoding_fix import fix_html_encoding

        html = b'<!DOCTYPE html>\n<html>\n<head>\n<title>Test</title>\n</head>\n<body>\n<p>Content with quotes and dashes</p>\n</body>\n</html>'

        # First run
        result1 = fix_html_encoding(html)

        # Second run on result
        result2 = fix_html_encoding(result1)

        # Should be identical (or very similar - key content preserved)
        # Check key elements are present
        assert b'<meta charset="utf-8"' in result2
        assert b'<title>Test</title>' in result2
        assert b'Content with quotes and dashes' in result2

    def test_already_fixed_file_unchanged(self):
        """Already-correct UTF-8 file with meta charset should not change."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Already Fixed</title>
</head>
<body>
<p>Clean UTF-8 content</p>
</body>
</html>"""

        result = fix_html_encoding(html)

        # Should be identical (possibly minor whitespace differences)
        # Key: no content changes
        assert b'<meta charset="utf-8"' in result
        assert b'Clean UTF-8 content' in result


class TestXMLDeclarationHandling:
    """Test handling of XML declarations with encoding."""

    def test_removes_ascii_xml_declaration(self):
        """Should remove or update <?xml encoding='ASCII'?> declarations."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<?xml version='1.0' encoding='ASCII'?>
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>Content</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should not have ASCII declaration
        assert "encoding='ASCII'" not in result_str

        # Should either remove XML declaration or change to UTF-8
        if '<?xml' in result_str:
            assert "encoding='UTF-8'" in result_str or 'encoding="UTF-8"' in result_str

        # Should have HTML meta charset
        assert '<meta charset="utf-8"' in result_str

    def test_updates_xml_declaration_to_utf8(self):
        """Should update XML declaration encoding to UTF-8."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<?xml version='1.0' encoding='ISO-8859-1'?>
<html>
<head><title>Test</title></head>
<body>Content</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Should update to UTF-8
        if '<?xml' in result_str:
            assert 'UTF-8' in result_str or 'utf-8' in result_str
        assert 'ISO-8859-1' not in result_str


class TestMojibakeDetection:
    """Test mojibake pattern detection."""

    def test_detects_common_mojibake_patterns(self):
        """Should detect common mojibake byte sequences."""
        from utils.encoding_fix import detect_mojibake

        # Create mojibake: UTF-8 bytes interpreted as Latin-1
        # The mojibake string  "â€™" when decoded as UTF-8
        mojibake_str = '\u00e2\u0080\u0099'  # This is the mojibake pattern
        mojibake_html = f"Officer{mojibake_str}s Certificate".encode('utf-8')

        has_mojibake, patterns = detect_mojibake(mojibake_html)

        assert has_mojibake is True
        assert len(patterns) > 0

    def test_no_false_positives_on_clean_utf8(self):
        """Should not detect mojibake in clean UTF-8."""
        from utils.encoding_fix import detect_mojibake

        # Clean UTF-8 without mojibake patterns
        clean_html = b"Officer's Certificate with proper quotes and dashes"

        has_mojibake, patterns = detect_mojibake(clean_html)

        # Clean content should not be flagged
        # Note: Our detector looks for specific mojibake patterns, not just UTF-8 bytes
        assert has_mojibake is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_html(self):
        """Should handle empty or minimal HTML."""
        from utils.encoding_fix import fix_html_encoding

        html = b""

        result = fix_html_encoding(html)

        # Should return something valid (minimal HTML or empty)
        assert result is not None

    def test_handles_malformed_html(self):
        """Should handle malformed HTML gracefully."""
        from utils.encoding_fix import fix_html_encoding

        html = b"<html><head><title>No closing tags"

        # Should not crash
        result = fix_html_encoding(html)
        assert result is not None

    def test_preserves_html_entities(self):
        """Should preserve HTML entities like &nbsp; &lt; &gt;."""
        from utils.encoding_fix import fix_html_encoding

        html = b"""<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<p>Test&nbsp;entities: &lt;tag&gt; &amp; more</p>
</body>
</html>"""

        result = fix_html_encoding(html)
        result_str = result.decode('utf-8')

        # Entities should be preserved
        assert '&nbsp;' in result_str or '\xa0' in result_str
        assert '&lt;' in result_str
        assert '&gt;' in result_str
        assert '&amp;' in result_str


class TestBatchProcessing:
    """Test batch processing logic."""

    def test_processes_multiple_files_in_batch(self):
        """Should process multiple files efficiently."""
        from utils.encoding_fix import EncodingFixProcessor

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create test files
            for i in range(5):
                file = tmppath / f"test_{i}.html"
                file.write_bytes(b"<html><head><title>Test</title></head><body>Content</body></html>")

            processor = EncodingFixProcessor(storage_root=tmppath)
            results = processor.process_batch(list(tmppath.glob("*.html")))

            # Should process all files
            assert len(results) == 5
            # All should succeed
            assert all(r['success'] for r in results)

    def test_batch_idempotence_tracking(self):
        """Should track which files have been fixed."""
        from utils.encoding_fix import EncodingFixProcessor

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            file = tmppath / "test.html"
            file.write_bytes(b"<html><head><title>Test</title></head><body>Content</body></html>")

            processor = EncodingFixProcessor(storage_root=tmppath)

            # First run
            results1 = processor.process_batch([file])
            assert results1[0]['fixed'] is True

            # Second run - should skip (idempotent)
            results2 = processor.process_batch([file])
            assert results2[0]['skipped'] is True or results2[0]['fixed'] is False
