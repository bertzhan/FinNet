"""
Tests for parse_filings() date conversion bug fix.

Verifies that report_date and filing_date are properly converted
to datetime.date objects, preventing AttributeError when .year is called.
"""
import pytest
from datetime import date, datetime
from services.sec_api import SECAPIClient, _to_date_or_none


class TestDateConversionHelper:
    """Test the _to_date_or_none helper function."""

    def test_convert_iso_dash_format(self):
        """Test conversion of YYYY-MM-DD format."""
        result = _to_date_or_none("2025-03-31")
        assert result == date(2025, 3, 31)

    def test_convert_iso_compact_format(self):
        """Test conversion of YYYYMMDD format."""
        result = _to_date_or_none("20250331")
        assert result == date(2025, 3, 31)

    def test_convert_none_returns_none(self):
        """Test that None input returns None."""
        result = _to_date_or_none(None)
        assert result is None

    def test_convert_empty_string_returns_none(self):
        """Test that empty string returns None."""
        result = _to_date_or_none("")
        assert result is None

    def test_convert_malformed_date_returns_none(self):
        """Test that malformed date strings return None."""
        # European format (not supported)
        result = _to_date_or_none("31/03/2025")
        assert result is None

        # Invalid format
        result = _to_date_or_none("March 31, 2025")
        assert result is None

        # Garbage
        result = _to_date_or_none("not-a-date")
        assert result is None

    def test_convert_already_date_object(self):
        """Test that date objects are returned as-is."""
        input_date = date(2025, 3, 31)
        result = _to_date_or_none(input_date)
        assert result == input_date
        assert result is input_date  # Same object


class TestParseFilingsDates:
    """Test parse_filings() date conversion."""

    def create_mock_submissions(self, filing_date_str="2024-03-15", report_date_str="2023-12-31"):
        """Create mock SEC submissions data."""
        return {
            "cik": "0001234567",
            "filings": {
                "recent": {
                    "accessionNumber": ["0001234567-24-000001"],
                    "form": ["10-K"],
                    "filingDate": [filing_date_str],
                    "reportDate": [report_date_str],
                    "primaryDocument": ["form10k.htm"],
                }
            }
        }

    def test_filing_date_converted_to_date_object(self):
        """Test that filing_date is converted to date object."""
        client = SECAPIClient()
        submissions = self.create_mock_submissions(filing_date_str="2024-03-15")

        filings = client.parse_filings(
            submissions,
            form_types=['10-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1
        assert isinstance(filings[0]['filing_date'], date)
        assert filings[0]['filing_date'] == date(2024, 3, 15)

    def test_report_date_converted_to_date_object(self):
        """Test that report_date is converted to date object (BUG FIX)."""
        client = SECAPIClient()
        submissions = self.create_mock_submissions(report_date_str="2023-12-31")

        filings = client.parse_filings(
            submissions,
            form_types=['10-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1
        # This is the key assertion - report_date must be a date object, not a string
        assert isinstance(filings[0]['report_date'], date)
        assert filings[0]['report_date'] == date(2023, 12, 31)

    def test_report_date_none_when_missing(self):
        """Test that report_date is None when missing from API response."""
        client = SECAPIClient()
        submissions = {
            "cik": "0001234567",
            "filings": {
                "recent": {
                    "accessionNumber": ["0001234567-24-000001"],
                    "form": ["10-Q"],
                    "filingDate": ["2024-03-15"],
                    # reportDate field missing entirely
                    "primaryDocument": ["form10q.htm"],
                }
            }
        }

        filings = client.parse_filings(
            submissions,
            form_types=['10-Q'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1
        assert filings[0]['report_date'] is None

    def test_report_date_none_when_null_in_array(self):
        """Test that report_date is None when null in API array."""
        client = SECAPIClient()
        submissions = {
            "cik": "0001234567",
            "filings": {
                "recent": {
                    "accessionNumber": ["0001234567-24-000001"],
                    "form": ["8-K"],
                    "filingDate": ["2024-03-15"],
                    "reportDate": [None],  # Explicit None
                    "primaryDocument": ["form8k.htm"],
                }
            }
        }

        filings = client.parse_filings(
            submissions,
            form_types=['8-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1
        assert filings[0]['report_date'] is None

    def test_malformed_report_date_returns_none(self):
        """Test that malformed report_date strings are converted to None."""
        client = SECAPIClient()
        submissions = self.create_mock_submissions(report_date_str="invalid-date")

        filings = client.parse_filings(
            submissions,
            form_types=['10-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1
        assert filings[0]['report_date'] is None

    def test_no_attribute_error_on_year_access(self):
        """Test that .year can be safely called on report_date."""
        client = SECAPIClient()
        submissions = self.create_mock_submissions(
            filing_date_str="2024-03-15",
            report_date_str="2023-12-31"
        )

        filings = client.parse_filings(
            submissions,
            form_types=['10-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1

        # This should not raise AttributeError
        filing = filings[0]
        report_date = filing.get('report_date') or filing['filing_date']
        fiscal_year = report_date.year

        assert fiscal_year == 2023

    def test_fallback_to_filing_date_when_report_date_none(self):
        """Test fallback pattern used in backfill_foreign.py."""
        client = SECAPIClient()
        submissions = {
            "cik": "0001234567",
            "filings": {
                "recent": {
                    "accessionNumber": ["0001234567-24-000001"],
                    "form": ["6-K"],
                    "filingDate": ["2024-03-15"],
                    "reportDate": [None],
                    "primaryDocument": ["form6k.htm"],
                }
            }
        }

        filings = client.parse_filings(
            submissions,
            form_types=['6-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1

        # Simulate the fallback pattern from backfill_foreign.py line 395
        filing = filings[0]
        ref_date = filing.get('report_date') or filing['filing_date']
        fiscal_year = ref_date.year

        # Should use filing_date since report_date is None
        assert fiscal_year == 2024
        assert ref_date == filing['filing_date']

    def test_compact_format_report_date(self):
        """Test that compact YYYYMMDD format is supported."""
        client = SECAPIClient()
        submissions = self.create_mock_submissions(report_date_str="20231231")

        filings = client.parse_filings(
            submissions,
            form_types=['10-K'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 1
        assert isinstance(filings[0]['report_date'], date)
        assert filings[0]['report_date'] == date(2023, 12, 31)

    def test_multiple_filings_all_dates_converted(self):
        """Test that all filings in a batch have dates converted."""
        client = SECAPIClient()
        submissions = {
            "cik": "0001234567",
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0001234567-24-000001",
                        "0001234567-23-000099",
                        "0001234567-24-000002",
                    ],
                    "form": ["10-K", "10-Q", "10-Q"],
                    "filingDate": ["2024-03-15", "2023-08-10", "2024-05-15"],
                    "reportDate": ["2023-12-31", "2023-06-30", None],
                    "primaryDocument": ["form10k.htm", "form10q.htm", "form10q.htm"],
                }
            }
        }

        filings = client.parse_filings(
            submissions,
            form_types=['10-K', '10-Q'],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        assert len(filings) == 3

        # Check all filing dates are date objects
        for filing in filings:
            assert isinstance(filing['filing_date'], date)

        # Check report dates
        assert isinstance(filings[0]['report_date'], date)
        assert filings[0]['report_date'] == date(2023, 12, 31)

        assert isinstance(filings[1]['report_date'], date)
        assert filings[1]['report_date'] == date(2023, 6, 30)

        assert filings[2]['report_date'] is None  # Was None in input
