#!/usr/bin/env python3
"""
Download SEC Filings from Company CSV

Standalone script that reads a CSV of companies and downloads their filing metadata.
No database required - saves results to JSON/CSV files.

Usage:
    # Download filings for first 10 companies
    python scripts/download_filings_from_csv.py --input my_companies.csv --limit 10

    # Download all 10-K and 10-Q filings for 2024
    python scripts/download_filings_from_csv.py --input my_companies.csv --year 2024

    # Download specific form types
    python scripts/download_filings_from_csv.py --input my_companies.csv --forms 10-K,10-Q --limit 5

    # Download for specific tickers
    python scripts/download_filings_from_csv.py --input my_companies.csv --tickers AAPL,MSFT,GOOGL
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import structlog

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sec_api import SECAPIClient

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


def load_companies_from_csv(csv_path: str, ticker_filter: Optional[List[str]] = None) -> List[dict]:
    """
    Load companies from CSV file.

    Args:
        csv_path: Path to CSV file with columns: cik, ticker, company_name
        ticker_filter: Optional list of tickers to filter by

    Returns:
        List of company dictionaries
    """
    companies = []

    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            # Filter by ticker if specified
            if ticker_filter and row['ticker'] not in ticker_filter:
                continue

            companies.append({
                'cik': row['cik'],
                'ticker': row['ticker'],
                'company_name': row['company_name']
            })

    logger.info("companies_loaded_from_csv", path=csv_path, count=len(companies))
    return companies


def download_company_filings(
    client: SECAPIClient,
    company: dict,
    form_types: List[str],
    start_date: datetime,
    end_date: datetime
) -> dict:
    """
    Download filings for a single company.

    Args:
        client: SEC API client
        company: Company dict with cik, ticker, company_name
        form_types: List of form types to fetch (e.g., ['10-K', '10-Q'])
        start_date: Start date for filings
        end_date: End date for filings

    Returns:
        Dictionary with company info and filings
    """
    logger.info(
        "fetching_company_filings",
        ticker=company['ticker'],
        cik=company['cik'],
        forms=form_types
    )

    try:
        # Fetch submissions from SEC
        submissions = client.fetch_company_submissions(company['cik'])

        # Parse filings
        filings = client.parse_filings(
            submissions,
            form_types=form_types,
            start_date=start_date,
            end_date=end_date
        )

        # Convert date objects to strings for JSON serialization
        filings_serializable = []
        for filing in filings:
            filing_copy = filing.copy()
            if 'filing_date' in filing_copy and filing_copy['filing_date']:
                filing_copy['filing_date'] = filing_copy['filing_date'].isoformat()
            if 'report_date' in filing_copy and filing_copy['report_date']:
                filing_copy['report_date'] = filing_copy['report_date'].isoformat()
            filings_serializable.append(filing_copy)

        result = {
            'cik': company['cik'],
            'ticker': company['ticker'],
            'company_name': company['company_name'],
            'filings_count': len(filings_serializable),
            'filings': filings_serializable
        }

        logger.info(
            "company_filings_fetched",
            ticker=company['ticker'],
            filings_found=len(filings_serializable)
        )

        return result

    except Exception as e:
        logger.error(
            "company_filings_fetch_failed",
            ticker=company['ticker'],
            cik=company['cik'],
            error=str(e)
        )

        return {
            'cik': company['cik'],
            'ticker': company['ticker'],
            'company_name': company['company_name'],
            'filings_count': 0,
            'filings': [],
            'error': str(e)
        }


def save_results_to_json(results: List[dict], output_path: str):
    """Save results to JSON file."""
    output = {
        'downloaded_at': datetime.utcnow().isoformat(),
        'companies_count': len(results),
        'total_filings': sum(r['filings_count'] for r in results),
        'companies': results
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    logger.info(
        "results_saved_to_json",
        path=output_path,
        companies=len(results),
        total_filings=output['total_filings']
    )


def save_results_to_csv(results: List[dict], output_path: str):
    """Save flattened results to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'ticker',
            'cik',
            'company_name',
            'accession_number',
            'form_type',
            'filing_date',
            'report_date',
            'primary_document',
            'is_amendment'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        total_filings = 0
        for company_result in results:
            for filing in company_result.get('filings', []):
                writer.writerow({
                    'ticker': company_result['ticker'],
                    'cik': company_result['cik'],
                    'company_name': company_result['company_name'],
                    'accession_number': filing.get('accession_number', ''),
                    'form_type': filing.get('form_type', ''),
                    'filing_date': filing.get('filing_date', ''),
                    'report_date': filing.get('report_date', ''),
                    'primary_document': filing.get('primary_document', ''),
                    'is_amendment': filing.get('is_amendment', False)
                })
                total_filings += 1

    logger.info(
        "results_saved_to_csv",
        path=output_path,
        companies=len(results),
        total_filings=total_filings
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Download SEC filings from company CSV (no database required)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download filings for first 10 companies
  python scripts/download_filings_from_csv.py --input my_companies.csv --limit 10

  # Download all 10-K filings for 2024
  python scripts/download_filings_from_csv.py --input my_companies.csv --forms 10-K --year 2024

  # Download for specific tickers
  python scripts/download_filings_from_csv.py --input my_companies.csv --tickers AAPL,MSFT,GOOGL

  # Custom output file
  python scripts/download_filings_from_csv.py --input my_companies.csv --output my_filings.json --limit 5

Output:
  - JSON file with full filing metadata (default)
  - CSV file with flattened filing list (use --format csv)
        """
    )

    parser.add_argument(
        '--input',
        required=True,
        help='Input CSV file with columns: cik, ticker, company_name'
    )

    parser.add_argument(
        '--output',
        help='Output file path (default: sec_filings.json or sec_filings.csv)'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'csv'],
        default='json',
        help='Output format (default: json)'
    )

    parser.add_argument(
        '--forms',
        default='10-K,10-Q',
        help='Comma-separated form types (default: 10-K,10-Q)'
    )

    parser.add_argument(
        '--year',
        type=int,
        help='Specific year to download (e.g., 2024). Default: 2023-2025'
    )

    parser.add_argument(
        '--start-date',
        help='Start date in YYYY-MM-DD format (overrides --year)'
    )

    parser.add_argument(
        '--end-date',
        help='End date in YYYY-MM-DD format (overrides --year)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of companies to process (for testing)'
    )

    parser.add_argument(
        '--tickers',
        help='Comma-separated list of tickers to filter (e.g., AAPL,MSFT,GOOGL)'
    )

    args = parser.parse_args()

    # Parse form types
    form_types = [f.strip() for f in args.forms.split(',')]

    # Determine date range
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    elif args.year:
        start_date = datetime(args.year, 1, 1)
        end_date = datetime(args.year, 12, 31)
    else:
        # Default: 2023-2025
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2025, 12, 31)

    # Parse ticker filter
    ticker_filter = None
    if args.tickers:
        ticker_filter = [t.strip().upper() for t in args.tickers.split(',')]

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = f"sec_filings.{args.format}"

    # Load companies from CSV
    try:
        companies = load_companies_from_csv(args.input, ticker_filter)
    except FileNotFoundError:
        logger.error("csv_file_not_found", path=args.input)
        print(f"\n✗ Error: CSV file not found: {args.input}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("csv_load_failed", error=str(e), exc_info=True)
        print(f"\n✗ Error loading CSV: {e}", file=sys.stderr)
        return 1

    if not companies:
        logger.error("no_companies_loaded")
        print("\n✗ No companies loaded from CSV", file=sys.stderr)
        return 1

    # Apply limit if specified
    if args.limit:
        companies = companies[:args.limit]

    logger.info(
        "starting_filings_download",
        companies=len(companies),
        form_types=form_types,
        start_date=start_date.date(),
        end_date=end_date.date()
    )

    # Initialize SEC API client
    client = SECAPIClient(use_cache=False)

    # Download filings for each company
    results = []
    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}] Processing {company['ticker']} ({company['company_name']})...")

        result = download_company_filings(
            client,
            company,
            form_types,
            start_date,
            end_date
        )
        results.append(result)

        # Progress update
        print(f"  → Found {result['filings_count']} filings")

    # Save results
    try:
        if args.format == 'json':
            save_results_to_json(results, output_path)
        else:
            save_results_to_csv(results, output_path)

        # Success summary
        total_filings = sum(r['filings_count'] for r in results)
        print(f"\n✓ Successfully processed {len(results)} companies")
        print(f"✓ Total filings found: {total_filings}")
        print(f"✓ Saved to: {output_path}")

        return 0

    except Exception as e:
        logger.error("save_failed", error=str(e), exc_info=True)
        print(f"\n✗ Failed to save results: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
