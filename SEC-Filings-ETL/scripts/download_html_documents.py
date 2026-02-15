#!/usr/bin/env python3
"""
Download SEC HTML Documents and Images from JSON metadata

Standalone script that downloads actual HTML filings and embedded images.
No database required - reads from JSON/CSV metadata files.

Usage:
    # Download all filings from JSON
    python scripts/download_html_documents.py --input test_filings.json

    # Test with limit
    python scripts/download_html_documents.py --input test_filings.json --limit 5

    # Download without images
    python scripts/download_html_documents.py --input test_filings.json --no-images

    # Custom output directory
    python scripts/download_html_documents.py --input test_filings.json --output-dir /path/to/output
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from utils import sha256_bytes

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

SEC_BASE_URL = "https://www.sec.gov"


class SimpleRateLimiter:
    """Simple rate limiter for SEC API (10 req/s)."""

    def __init__(self, requests_per_second: int = 10):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()


def load_filings_from_json(json_path: str) -> List[dict]:
    """
    Load filing metadata from JSON file.

    Args:
        json_path: Path to JSON file (output from download_filings_from_csv.py)

    Returns:
        List of filing records with company info
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    filings = []
    for company in data.get('companies', []):
        ticker = company['ticker']
        cik = company['cik']
        company_name = company['company_name']

        for filing in company.get('filings', []):
            filings.append({
                'ticker': ticker,
                'cik': cik,
                'company_name': company_name,
                'accession_number': filing['accession_number'],
                'form_type': filing['form_type'],
                'filing_date': filing['filing_date'],
                'report_date': filing.get('report_date'),
                'primary_document': filing['primary_document'],
                'is_amendment': filing.get('is_amendment', False)
            })

    logger.info("filings_loaded_from_json", path=json_path, count=len(filings))
    return filings


def construct_document_url(cik: str, accession: str, filename: str) -> str:
    """
    Construct SEC EDGAR document URL.

    Args:
        cik: Company CIK (will strip leading zeros)
        accession: Accession number (with dashes)
        filename: Document filename

    Returns:
        Full URL to document
    """
    # Strip leading zeros from CIK
    cik_clean = str(int(cik))

    # Remove dashes from accession number
    accession_clean = accession.replace('-', '')

    url = f"{SEC_BASE_URL}/Archives/edgar/data/{cik_clean}/{accession_clean}/{filename}"
    return url


def determine_fiscal_period(form_type: str, report_date: Optional[str]) -> str:
    """
    Determine fiscal period from form type and report date.

    Args:
        form_type: Form type (10-K or 10-Q)
        report_date: Report date in ISO format (YYYY-MM-DD)

    Returns:
        Fiscal period: 'FY', 'Q1', 'Q2', 'Q3', or 'Q4'
    """
    if '10-K' in form_type or '20-F' in form_type or '40-F' in form_type:
        return 'FY'

    # For 10-Q, determine quarter from month
    if report_date:
        try:
            month = int(report_date.split('-')[1])
            if month in [1, 2, 3]:
                return 'Q1'
            elif month in [4, 5, 6]:
                return 'Q2'
            elif month in [7, 8, 9]:
                return 'Q3'
            else:
                return 'Q4'
        except:
            pass

    return 'Q4'  # Default


def construct_local_path(
    ticker: str,
    fiscal_year: int,
    fiscal_period: str,
    filing_date: str,
    exchange: str = "UNKNOWN"
) -> str:
    """
    Construct local file path following standard convention.

    Args:
        ticker: Ticker symbol
        fiscal_year: Fiscal year
        fiscal_period: Fiscal period (FY, Q1, Q2, Q3, Q4)
        filing_date: Filing date in ISO format (YYYY-MM-DD)
        exchange: Exchange name (default: UNKNOWN)

    Returns:
        Relative path: {EXCHANGE}/{TICKER}/{YEAR}/{TICKER}_{YEAR}_{PERIOD}_{DATE}.html
    """
    # Convert ISO date to DD-MM-YYYY format
    try:
        date_parts = filing_date.split('-')
        filing_date_formatted = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
    except:
        filing_date_formatted = filing_date.replace('-', '')

    filename = f"{ticker}_{fiscal_year}_{fiscal_period}_{filing_date_formatted}.html"
    path = f"{exchange}/{ticker}/{fiscal_year}/{filename}"
    return path


def extract_image_urls(html_content: bytes, base_url: str) -> List[str]:
    """
    Extract all image URLs from HTML content.

    Args:
        html_content: Raw HTML bytes
        base_url: Base URL for resolving relative URLs

    Returns:
        List of absolute image URLs
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        img_tags = soup.find_all('img')

        urls = []
        for img in img_tags:
            src = img.get('src')
            if src:
                # Resolve relative URLs
                if src.startswith('http'):
                    full_url = src
                elif src.startswith('/'):
                    full_url = urljoin(SEC_BASE_URL, src)
                else:
                    full_url = urljoin(base_url, src)

                urls.append(full_url)

        return urls
    except Exception as e:
        logger.warning("image_extraction_failed", error=str(e))
        return []


def rewrite_image_paths(html_content: bytes, image_mapping: Dict[str, str]) -> bytes:
    """
    Rewrite image paths in HTML to local relative paths.

    Args:
        html_content: Original HTML bytes
        image_mapping: Dict mapping original URL -> local relative path

    Returns:
        Modified HTML bytes with local image paths
    """
    try:
        # Parse with lxml to preserve encoding
        soup = BeautifulSoup(html_content, 'lxml')

        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src')
            if not src:
                continue

            # Normalize URL for lookup
            if src.startswith('/'):
                full_url = urljoin(SEC_BASE_URL, src)
            elif not src.startswith('http'):
                # Skip data URLs and other non-http URLs
                continue
            else:
                full_url = src

            # Replace with local path if available
            if full_url in image_mapping:
                local_path = image_mapping[full_url]
                img['src'] = f"./{Path(local_path).name}"

        # Return modified HTML as bytes
        return str(soup).encode('utf-8')
    except Exception as e:
        logger.error("html_rewrite_failed", error=str(e))
        return html_content


def download_html_document(
    filing: dict,
    output_dir: Path,
    download_images: bool,
    rate_limiter: SimpleRateLimiter,
    http_client: httpx.Client
) -> dict:
    """
    Download HTML document and optionally its images.

    Args:
        filing: Filing metadata dict
        output_dir: Base output directory
        download_images: Whether to download embedded images
        rate_limiter: Rate limiter instance
        http_client: HTTP client instance

    Returns:
        Result dict with status and paths
    """
    ticker = filing['ticker']
    cik = filing['cik']
    accession = filing['accession_number']
    primary_doc = filing['primary_document']
    form_type = filing['form_type']
    filing_date = filing['filing_date']
    report_date = filing.get('report_date') or filing_date

    # Determine fiscal year and period
    fiscal_year = int(report_date.split('-')[0])
    fiscal_period = determine_fiscal_period(form_type, report_date)

    # Construct local path
    local_path = construct_local_path(ticker, fiscal_year, fiscal_period, filing_date)
    full_path = output_dir / local_path

    # Skip if already exists
    if full_path.exists():
        logger.info("html_already_exists", path=str(full_path))
        return {
            'status': 'skipped',
            'ticker': ticker,
            'form_type': form_type,
            'path': str(full_path),
            'images_downloaded': 0
        }

    # Create directory
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Construct URL
    html_url = construct_document_url(cik, accession, primary_doc)

    logger.info(
        "downloading_html",
        ticker=ticker,
        form_type=form_type,
        url=html_url,
        local_path=local_path
    )

    try:
        # Rate limit
        rate_limiter.wait()

        # Download HTML
        response = http_client.get(
            html_url,
            headers={"User-Agent": settings.sec_user_agent},
            timeout=30.0,
            follow_redirects=True
        )
        response.raise_for_status()

        html_content = response.content
        html_size = len(html_content)

        images_downloaded = 0
        image_mapping = {}

        # Download images if enabled
        if download_images:
            image_urls = extract_image_urls(html_content, html_url)

            if image_urls:
                logger.info("found_images", count=len(image_urls))

                for i, img_url in enumerate(image_urls, 1):
                    try:
                        # Rate limit
                        rate_limiter.wait()

                        # Download image
                        img_response = http_client.get(
                            img_url,
                            headers={"User-Agent": settings.sec_user_agent},
                            timeout=30.0,
                            follow_redirects=True
                        )
                        img_response.raise_for_status()

                        img_content = img_response.content

                        # Determine extension
                        ext = Path(urlparse(img_url).path).suffix or '.png'

                        # Construct local image path
                        html_base = local_path.rsplit('.', 1)[0]
                        img_local_path = f"{html_base}_image-{i:03d}{ext}"
                        img_full_path = output_dir / img_local_path

                        # Save image
                        img_full_path.write_bytes(img_content)
                        image_mapping[img_url] = img_local_path
                        images_downloaded += 1

                        logger.debug(
                            "image_downloaded",
                            url=img_url,
                            path=img_local_path,
                            size=len(img_content)
                        )

                    except Exception as e:
                        logger.warning(
                            "image_download_failed",
                            url=img_url,
                            error=str(e)
                        )

                # Rewrite HTML with local image paths
                if image_mapping:
                    html_content = rewrite_image_paths(html_content, image_mapping)

        # Save HTML
        full_path.write_bytes(html_content)

        logger.info(
            "html_downloaded",
            ticker=ticker,
            form_type=form_type,
            path=str(full_path),
            size=html_size,
            images=images_downloaded
        )

        return {
            'status': 'downloaded',
            'ticker': ticker,
            'form_type': form_type,
            'path': str(full_path),
            'size': html_size,
            'images_downloaded': images_downloaded
        }

    except Exception as e:
        logger.error(
            "html_download_failed",
            ticker=ticker,
            url=html_url,
            error=str(e)
        )

        return {
            'status': 'failed',
            'ticker': ticker,
            'form_type': form_type,
            'url': html_url,
            'error': str(e)
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Download SEC HTML documents and images from JSON metadata (no database required)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all filings from JSON
  python scripts/download_html_documents.py --input test_filings.json

  # Test with 5 filings
  python scripts/download_html_documents.py --input test_filings.json --limit 5

  # Download without images
  python scripts/download_html_documents.py --input test_filings.json --no-images

  # Custom output directory
  python scripts/download_html_documents.py --input test_filings.json --output-dir /path/to/output

Output:
  Files are saved to: {output-dir}/{EXCHANGE}/{TICKER}/{YEAR}/
  - {TICKER}_{YEAR}_{PERIOD}_{DATE}.html
  - {TICKER}_{YEAR}_{PERIOD}_{DATE}_image-001.gif
  - {TICKER}_{YEAR}_{PERIOD}_{DATE}_image-002.png
        """
    )

    parser.add_argument(
        '--input',
        required=True,
        help='Input JSON file with filing metadata (from download_filings_from_csv.py)'
    )

    parser.add_argument(
        '--output-dir',
        default='data/filings',
        help='Output directory for downloaded files (default: data/filings)'
    )

    parser.add_argument(
        '--no-images',
        action='store_true',
        help='Skip downloading images (HTML only)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of filings to download (for testing)'
    )

    args = parser.parse_args()

    download_images = not args.no_images

    # Load filings from JSON
    try:
        filings = load_filings_from_json(args.input)
    except FileNotFoundError:
        logger.error("json_file_not_found", path=args.input)
        print(f"\n✗ Error: JSON file not found: {args.input}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("json_load_failed", error=str(e), exc_info=True)
        print(f"\n✗ Error loading JSON: {e}", file=sys.stderr)
        return 1

    if not filings:
        logger.error("no_filings_loaded")
        print("\n✗ No filings found in JSON", file=sys.stderr)
        return 1

    # Apply limit if specified
    if args.limit:
        filings = filings[:args.limit]

    # Prepare output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "starting_download",
        filings=len(filings),
        output_dir=str(output_dir),
        download_images=download_images
    )

    # Initialize HTTP client and rate limiter
    http_client = httpx.Client(http2=True)
    rate_limiter = SimpleRateLimiter(requests_per_second=settings.sec_rps)

    # Download filings
    results = {
        'downloaded': 0,
        'skipped': 0,
        'failed': 0,
        'total_images': 0
    }

    try:
        for i, filing in enumerate(filings, 1):
            print(f"\n[{i}/{len(filings)}] {filing['ticker']} - {filing['form_type']} ({filing['filing_date']})")

            result = download_html_document(
                filing,
                output_dir,
                download_images,
                rate_limiter,
                http_client
            )

            # Update stats
            results[result['status']] += 1
            if result['status'] == 'downloaded':
                results['total_images'] += result.get('images_downloaded', 0)
                print(f"  ✓ Downloaded: {result['path']}")
                if result.get('images_downloaded', 0) > 0:
                    print(f"    → {result['images_downloaded']} images")
            elif result['status'] == 'skipped':
                print(f"  ⊘ Skipped (already exists)")
            else:
                print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")

    finally:
        http_client.close()

    # Summary
    print("\n" + "="*60)
    print("Download Summary")
    print("="*60)
    print(f"Total filings:    {len(filings)}")
    print(f"Downloaded:       {results['downloaded']}")
    print(f"Skipped:          {results['skipped']}")
    print(f"Failed:           {results['failed']}")
    print(f"Total images:     {results['total_images']}")
    print(f"Output directory: {output_dir.absolute()}")
    print("="*60)

    return 0 if results['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
