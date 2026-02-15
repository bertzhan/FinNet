"""
Unit tests for SEC EDGAR URL construction.

Tests ensure that URLs are built using the company's CIK (not accession prefix)
and that normalization (leading zeros, dashes) works correctly.
"""
import pytest
from services.sec_api import SECAPIClient


class TestURLConstruction:
    """Test suite for URL construction helpers."""

    def test_build_url_with_primary_doc_uses_company_cik(self):
        """
        Test that construct_primary_html_url uses the company CIK, not accession prefix.

        Bug fix verification: Previously used accession prefix (0000950170) instead
        of company CIK (0001766600), causing 404 errors on downloads.
        """
        client = SECAPIClient(use_cache=False)

        # SNDL example: CIK=0001766600, accession prefix=0000950170
        url = client.construct_primary_html_url(
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document="sndl-20241231.htm"
        )

        # Should use company CIK (1766600), not accession prefix (0000950170)
        assert "/data/1766600/" in url
        assert "/data/0000950170/" not in url
        assert url == "https://www.sec.gov/Archives/edgar/data/1766600/000095017025040545/sndl-20241231.htm"

    def test_build_url_without_primary_doc_falls_back_to_index(self):
        """Test that missing primary_document falls back to index.html."""
        client = SECAPIClient(use_cache=False)

        url = client.construct_primary_html_url(
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document=None
        )

        assert url.endswith("/index.html")
        assert url == "https://www.sec.gov/Archives/edgar/data/1766600/000095017025040545/index.html"

    def test_build_url_with_empty_primary_doc_falls_back_to_index(self):
        """Test that empty string primary_document falls back to index.html."""
        client = SECAPIClient(use_cache=False)

        url = client.construct_primary_html_url(
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document=""
        )

        assert url.endswith("/index.html")

    def test_build_url_with_whitespace_primary_doc_falls_back_to_index(self):
        """Test that whitespace-only primary_document falls back to index.html."""
        client = SECAPIClient(use_cache=False)

        url = client.construct_primary_html_url(
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document="   "
        )

        assert url.endswith("/index.html")

    def test_cik_normalization_strips_leading_zeros(self):
        """Test that leading zeros are removed from CIK in URL."""
        client = SECAPIClient(use_cache=False)

        # Various CIK formats with leading zeros
        test_cases = [
            ("0001766600", "1766600"),
            ("1766600", "1766600"),
            ("0000000123", "123"),
            ("00000320193", "320193"),  # AAPL
        ]

        for input_cik, expected_cik in test_cases:
            url = client.construct_primary_html_url(
                cik=input_cik,
                accession="0000950170-25-040545",
                primary_document="test.htm"
            )
            assert f"/data/{expected_cik}/" in url

    def test_accession_normalization_strips_dashes(self):
        """Test that dashes are removed from accession number in URL."""
        client = SECAPIClient(use_cache=False)

        url = client.construct_primary_html_url(
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document="test.htm"
        )

        # URL should contain accession without dashes
        assert "/000095017025040545/" in url
        assert "0000950170-25-040545" not in url

    def test_url_format_matches_sec_edgar_structure(self):
        """Test that URL follows SEC EDGAR archive structure."""
        client = SECAPIClient(use_cache=False)

        url = client.construct_primary_html_url(
            cik="0001639920",  # SPOT
            accession="0001639920-25-000003",
            primary_document="ck0001639920-20241231.htm"
        )

        # Expected format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}
        assert url.startswith("https://www.sec.gov/Archives/edgar/data/")
        assert "/1639920/" in url
        assert "/000163992025000003/" in url
        assert url.endswith("/ck0001639920-20241231.htm")

    def test_construct_document_url_uses_cik_correctly(self):
        """Test the existing construct_document_url method for consistency."""
        client = SECAPIClient(use_cache=False)

        url = client.construct_document_url(
            cik="0001766600",
            accession="0000950170-25-040545",
            filename="sndl-20241231.htm"
        )

        # Should use company CIK, not accession prefix
        assert "/data/1766600/" in url
        assert "/000095017025040545/" in url
        assert url.endswith("/sndl-20241231.htm")


class TestForeignBackfillURLGeneration:
    """Test URL generation in foreign backfill context."""

    def test_create_artifact_records_uses_company_cik(self):
        """Test that create_artifact_records passes CIK correctly."""
        from jobs.backfill_foreign import create_artifact_records

        artifacts = create_artifact_records(
            filing_id=1,
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document="sndl-20241231.htm",
            include_exhibits=False
        )

        assert len(artifacts) == 1
        artifact = artifacts[0]

        # Should use company CIK (1766600), not accession prefix (0000950170)
        assert "/data/1766600/" in artifact['url']
        assert "/data/0000950170/" not in artifact['url']
        assert artifact['url'] == "https://www.sec.gov/Archives/edgar/data/1766600/000095017025040545/sndl-20241231.htm"

    def test_create_artifact_records_with_none_primary_doc(self):
        """Test create_artifact_records with missing primary_document."""
        from jobs.backfill_foreign import create_artifact_records

        artifacts = create_artifact_records(
            filing_id=1,
            cik="0001766600",
            accession="0000950170-25-040545",
            primary_document=None,
            include_exhibits=False
        )

        assert len(artifacts) == 1
        artifact = artifacts[0]

        # Should fall back to index.html
        assert artifact['url'].endswith("/index.html")
        assert artifact['filename'] == "index.html"


class Test6KInclusionPolicy:
    """Test 6-K inclusion policy logic."""

    def test_6k_policy_off_excludes_all_6k(self):
        """Test that include_6k='off' excludes all 6-K filings."""
        from jobs.backfill_foreign import should_include_6k_filing

        result = should_include_6k_filing(
            form_type="6-K",
            has_financials=False,
            include_policy="off"
        )

        assert result['include'] is False
        assert result['include_exhibits'] is False

    def test_6k_policy_off_excludes_6k_with_financials(self):
        """Test that include_6k='off' excludes even 6-K with financials."""
        from jobs.backfill_foreign import should_include_6k_filing

        result = should_include_6k_filing(
            form_type="6-K",
            has_financials=True,
            include_policy="off"
        )

        assert result['include'] is False

    def test_6k_policy_minimal_includes_without_exhibits(self):
        """Test that include_6k='minimal' includes 6-K without exhibits."""
        from jobs.backfill_foreign import should_include_6k_filing

        result = should_include_6k_filing(
            form_type="6-K",
            has_financials=False,
            include_policy="minimal"
        )

        assert result['include'] is True
        assert result['include_exhibits'] is False

    def test_6k_policy_does_not_affect_20f_40f(self):
        """Test that 6-K policy doesn't affect 20-F/40-F filings."""
        from jobs.backfill_foreign import should_include_6k_filing

        for form_type in ["20-F", "20-F/A", "40-F", "40-F/A"]:
            result = should_include_6k_filing(
                form_type=form_type,
                has_financials=False,
                include_policy="off"
            )

            # Non-6K forms should always be included
            assert result['include'] is True
