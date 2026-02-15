"""
Test image mapping with real AAPL data to verify fix.
"""
import pytest
from pathlib import Path


class MockArtifact:
    """Mock artifact for testing."""

    def __init__(self, url, filename, local_path):
        self.url = url
        self.filename = filename
        self.local_path = local_path


class TestRealWorldImageMapping:
    """Test image mapping with actual AAPL data structure."""

    def test_aapl_filename_only_references(self):
        """Test AAPL case where HTML has filename-only image references."""

        # Real AAPL data from database
        artifacts = [
            MockArtifact(
                url="https://www.sec.gov/Archives/edgar/data/0000320193/000032019325000079/aapl-20250927_g1.jpg",
                filename="aapl-20250927_g1.jpg",
                local_path="NASDAQ/AAPL/2025/AAPL_2025_Q1_01-08-2025_image-001.jpg"
            ),
            MockArtifact(
                url="https://www.sec.gov/Archives/edgar/data/0000320193/000032019325000079/aapl-20250927_g2.jpg",
                filename="aapl-20250927_g2.jpg",
                local_path="NASDAQ/AAPL/2025/AAPL_2025_FY_31-10-2025_image-002.jpg"
            )
        ]

        # Real HTML content from AAPL filing
        html_content = b"""<?xml version='1.0' encoding='ASCII'?>
<html>
<body>
<table>
<tr><td><img src="aapl-20250927_g1.jpg" style="width:100%"/></td></tr>
<tr><td><img src="aapl-20250927_g2.jpg"/></td></tr>
</table>
</body>
</html>"""

        from utils.html_processor import process_html_preserve_encoding, build_image_replacement_mapping

        # Build mapping
        img_replacements = build_image_replacement_mapping(
            "https://www.sec.gov/Archives/edgar/data/0000320193/000032019325000079/aapl-20250927.htm",
            artifacts
        )

        # Verify mapping includes filename references
        assert "aapl-20250927_g1.jpg" in img_replacements
        assert "aapl-20250927_g2.jpg" in img_replacements

        # Verify correct local paths
        assert img_replacements["aapl-20250927_g1.jpg"] == "./AAPL_2025_Q1_01-08-2025_image-001.jpg"
        assert img_replacements["aapl-20250927_g2.jpg"] == "./AAPL_2025_FY_31-10-2025_image-002.jpg"

        # Process HTML
        result = process_html_preserve_encoding(html_content, img_replacements)

        # Verify images were rewritten
        result_str = result.decode('ascii', errors='replace')

        assert './AAPL_2025_Q1_01-08-2025_image-001.jpg' in result_str
        assert './AAPL_2025_FY_31-10-2025_image-002.jpg' in result_str

        # Verify old references are gone
        assert 'src="aapl-20250927_g1.jpg"' not in result_str
        assert 'src="aapl-20250927_g2.jpg"' not in result_str

    def test_mixed_url_and_filename_references(self):
        """Test case with both full URLs and filename-only references."""

        artifacts = [
            MockArtifact(
                url="https://www.sec.gov/edgar/data/123/image1.gif",
                filename="image1.gif",
                local_path="NYSE/XYZ/2025/XYZ_2025_Q1_01-01-2025_image-001.gif"
            ),
            MockArtifact(
                url="https://www.sec.gov/edgar/data/123/chart.png",
                filename="chart.png",
                local_path="NYSE/XYZ/2025/XYZ_2025_Q1_01-01-2025_image-002.png"
            )
        ]

        html_content = b"""<?xml version='1.0' encoding='ASCII'?>
<html>
<body>
<!-- Full URL reference -->
<img src="https://www.sec.gov/edgar/data/123/image1.gif"/>
<!-- Filename-only reference -->
<img src="chart.png"/>
<!-- Path reference -->
<img src="/edgar/data/123/image1.gif"/>
</body>
</html>"""

        from utils.html_processor import process_html_preserve_encoding, build_image_replacement_mapping

        img_replacements = build_image_replacement_mapping(
            "https://www.sec.gov/edgar/data/123/filing.html",
            artifacts
        )

        # Should have mappings for all reference types
        assert "https://www.sec.gov/edgar/data/123/image1.gif" in img_replacements
        assert "image1.gif" in img_replacements
        assert "/edgar/data/123/image1.gif" in img_replacements
        assert "chart.png" in img_replacements

        result = process_html_preserve_encoding(html_content, img_replacements)
        result_str = result.decode('ascii', errors='replace')

        # All three references should be rewritten to local paths
        assert result_str.count('./XYZ_2025_Q1_01-01-2025_image-001.gif') == 2  # Full URL + path reference
        assert './XYZ_2025_Q1_01-01-2025_image-002.png' in result_str

    def test_no_duplicate_image_elements(self):
        """Test that image rewriting doesn't duplicate img elements."""

        artifacts = [
            MockArtifact(
                url="https://sec.gov/img.gif",
                filename="img.gif",
                local_path="NASDAQ/TEST/2025/TEST_2025_Q1_01-01-2025_image-001.gif"
            )
        ]

        html_content = b"""<?xml version='1.0' encoding='ASCII'?>
<html><body>
<img src="img.gif"/>
</body></html>"""

        from utils.html_processor import process_html_preserve_encoding, build_image_replacement_mapping

        img_replacements = build_image_replacement_mapping("https://sec.gov/filing.html", artifacts)
        result = process_html_preserve_encoding(html_content, img_replacements)

        # Should have exactly 1 img tag
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(result, 'html.parser')
        img_tags = soup.find_all('img')

        assert len(img_tags) == 1
        assert img_tags[0].get('src') == './TEST_2025_Q1_01-01-2025_image-001.gif'
