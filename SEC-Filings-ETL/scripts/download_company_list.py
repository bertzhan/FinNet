#!/usr/bin/env python3
"""
Download SEC Company List to CSV

Standalone script that fetches all ~13k SEC-registered companies and exports to CSV.
No database required - pure API to CSV conversion.

Usage:
    python scripts/download_company_list.py
    python scripts/download_company_list.py --output my_companies.csv
    python scripts/download_company_list.py --format json
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import structlog

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sec_api import SECAPIClient
from config.settings import settings

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


def download_to_csv(output_path: str):
    """
    Download SEC company list and save to CSV.

    Args:
        output_path: Path to output CSV file
    """
    logger.info("starting_company_list_download", output_path=output_path)

    # Initialize SEC API client (no database needed)
    client = SECAPIClient(use_cache=False)

    # Fetch company tickers from SEC
    logger.info("fetching_company_tickers_from_sec")
    tickers_data = client.fetch_company_tickers()

    company_count = len(tickers_data)
    logger.info("company_tickers_fetched", count=company_count)

    # Convert to list and sort by ticker
    companies = []
    for key, company_data in tickers_data.items():
        companies.append({
            'cik': str(company_data['cik_str']).zfill(10),
            'ticker': company_data['ticker'].upper(),
            'company_name': company_data['title']
        })

    # Sort by ticker
    companies.sort(key=lambda x: x['ticker'])

    # Write to CSV
    logger.info("writing_csv", path=output_path, companies=len(companies))

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['cik', 'ticker', 'company_name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for company in companies:
            writer.writerow(company)

    logger.info(
        "company_list_download_completed",
        output_path=output_path,
        companies_written=len(companies),
        file_size_bytes=Path(output_path).stat().st_size
    )

    return len(companies)


def download_to_json(output_path: str):
    """
    Download SEC company list and save to JSON.

    Args:
        output_path: Path to output JSON file
    """
    logger.info("starting_company_list_download", output_path=output_path, format="json")

    # Initialize SEC API client
    client = SECAPIClient(use_cache=False)

    # Fetch company tickers from SEC
    logger.info("fetching_company_tickers_from_sec")
    tickers_data = client.fetch_company_tickers()

    company_count = len(tickers_data)
    logger.info("company_tickers_fetched", count=company_count)

    # Convert to list format
    companies = []
    for key, company_data in tickers_data.items():
        companies.append({
            'cik': str(company_data['cik_str']).zfill(10),
            'ticker': company_data['ticker'].upper(),
            'company_name': company_data['title']
        })

    # Sort by ticker
    companies.sort(key=lambda x: x['ticker'])

    # Write to JSON
    logger.info("writing_json", path=output_path, companies=len(companies))

    with open(output_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(
            {
                'downloaded_at': datetime.utcnow().isoformat(),
                'count': len(companies),
                'companies': companies
            },
            jsonfile,
            indent=2
        )

    logger.info(
        "company_list_download_completed",
        output_path=output_path,
        companies_written=len(companies),
        file_size_bytes=Path(output_path).stat().st_size
    )

    return len(companies)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Download SEC company list to CSV or JSON (no database required)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download to default file (sec_companies.csv)
  python scripts/download_company_list.py

  # Download to custom CSV file
  python scripts/download_company_list.py --output my_companies.csv

  # Download to JSON format
  python scripts/download_company_list.py --format json --output companies.json

  # Show current SEC User-Agent
  python scripts/download_company_list.py --show-config

Note:
  This script requires SEC_USER_AGENT to be configured in .env file.
  Example: SEC_USER_AGENT=YourName your.email@example.com
        """
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output file path (default: sec_companies.csv or sec_companies.json)'
    )

    parser.add_argument(
        '--format',
        choices=['csv', 'json'],
        default='csv',
        help='Output format (default: csv)'
    )

    parser.add_argument(
        '--show-config',
        action='store_true',
        help='Show SEC API configuration and exit'
    )

    args = parser.parse_args()

    # Show config if requested
    if args.show_config:
        print(f"SEC User-Agent: {settings.sec_user_agent}")
        print(f"SEC Rate Limit: {settings.sec_rps} requests/second")
        print(f"SEC Timeout: {settings.sec_timeout} seconds")
        return 0

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = f"sec_companies.{args.format}"

    try:
        # Download based on format
        if args.format == 'csv':
            company_count = download_to_csv(output_path)
        else:
            company_count = download_to_json(output_path)

        # Success summary
        print(f"\n✓ Successfully downloaded {company_count:,} companies")
        print(f"✓ Saved to: {output_path}")
        print(f"✓ File size: {Path(output_path).stat().st_size:,} bytes")

        return 0

    except Exception as e:
        logger.error("download_failed", error=str(e), exc_info=True)
        print(f"\n✗ Download failed: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
