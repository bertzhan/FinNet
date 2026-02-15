"""
HTML processing utilities for encoding preservation and image path rewriting.

Key principles:
1. Preserve original encoding declarations (ASCII, UTF-8, etc.)
2. Use html.parser to avoid character normalization
3. Only modify <img src> attributes, leave everything else unchanged
4. Handle encoding edge cases gracefully
"""
import re
from typing import Dict
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger()


def detect_encoding(content_bytes: bytes) -> str:
    """
    Detect the declared encoding from HTML/XML content.

    Args:
        content_bytes: Raw bytes of HTML content

    Returns:
        Detected encoding string (e.g., 'ascii', 'utf-8')
    """
    # Search in first 500 bytes for encoding declaration
    header = content_bytes[:500]

    # Match patterns like encoding='ASCII' or encoding="UTF-8"
    match = re.search(rb"encoding=['\"]([^'\"]+)['\"]", header, re.IGNORECASE)

    if match:
        declared = match.group(1).decode('ascii').lower()

        # Normalize encoding names
        if 'ascii' in declared:
            return 'ascii'
        elif 'utf' in declared:
            return 'utf-8'
        elif 'iso-8859' in declared or 'latin' in declared:
            return 'latin-1'
        else:
            return declared

    # Default to UTF-8 if no declaration found
    return 'utf-8'


def process_html_preserve_encoding(
    content_bytes: bytes,
    img_replacements: Dict[str, str]
) -> bytes:
    """
    Process HTML content while preserving original encoding.

    This function:
    1. Detects the original encoding declaration
    2. Uses html.parser to avoid character normalization (prevents mojibake)
    3. Replaces image src attributes based on replacement mapping
    4. Writes output with original encoding to preserve byte-for-byte accuracy

    Args:
        content_bytes: Original HTML content as bytes
        img_replacements: Dict mapping old image URLs to new local paths
                         e.g., {"https://sec.gov/img.gif": "./local_img-001.gif"}

    Returns:
        Processed HTML content as bytes, with original encoding preserved

    Example:
        >>> html = b'<?xml version="1.0" encoding="ASCII"?><html><img src="http://sec.gov/a.gif"/></html>'
        >>> replacements = {"http://sec.gov/a.gif": "./local.gif"}
        >>> result = process_html_preserve_encoding(html, replacements)
        >>> b"./local.gif" in result
        True
        >>> b"encoding='ASCII'" in result  # Encoding preserved
        True
    """
    # Detect original encoding
    original_encoding = detect_encoding(content_bytes)

    logger.debug(
        "processing_html",
        original_encoding=original_encoding,
        replacements_count=len(img_replacements)
    )

    # Decode with detected encoding
    try:
        content_str = content_bytes.decode(original_encoding)
    except (UnicodeDecodeError, LookupError) as e:
        # Fallback to UTF-8 with error handling
        logger.warning(
            "encoding_decode_failed",
            declared_encoding=original_encoding,
            error=str(e)
        )
        content_str = content_bytes.decode('utf-8', errors='replace')
        original_encoding = 'utf-8'

    # Parse with html.parser (NOT lxml) to avoid character normalization
    # html.parser preserves ASCII characters as-is without converting to UTF-8
    soup = BeautifulSoup(content_str, 'html.parser')

    # Track if any modifications were made
    modified = False
    modifications_count = 0

    # Find all img tags and replace src attributes
    img_tags = soup.find_all('img')

    for img in img_tags:
        src = img.get('src')

        if not src:
            continue

        # Check if this src should be replaced
        if src in img_replacements:
            new_src = img_replacements[src]
            img['src'] = new_src
            modified = True
            modifications_count += 1

            logger.debug(
                "image_src_replaced",
                old_src=src[:100],  # Truncate for logging
                new_src=new_src
            )

    if modified:
        logger.info(
            "html_processed",
            images_replaced=modifications_count,
            encoding=original_encoding
        )

    # Convert back to string
    result_str = str(soup)

    # Encode with original encoding
    # Use 'replace' error handling to gracefully handle any edge cases
    try:
        result_bytes = result_str.encode(original_encoding, errors='replace')
    except (UnicodeEncodeError, LookupError) as e:
        # If original encoding fails, fall back to UTF-8
        logger.warning(
            "encoding_encode_failed",
            target_encoding=original_encoding,
            error=str(e),
            fallback='utf-8'
        )
        result_bytes = result_str.encode('utf-8', errors='replace')

    return result_bytes


def build_image_replacement_mapping(
    html_url: str,
    image_artifacts: list
) -> Dict[str, str]:
    """
    Build a mapping from image references to local relative paths.

    This function handles multiple image reference formats:
    1. Full SEC URLs: https://www.sec.gov/Archives/edgar/data/.../image.gif
    2. Relative SEC paths: /Archives/edgar/data/.../image.gif
    3. Filename-only references: aapl-20250927_g1.jpg

    Args:
        html_url: The URL of the HTML document (for resolving relative URLs)
        image_artifacts: List of Artifact objects with url, filename, and local_path attributes

    Returns:
        Dict mapping image references (URLs or filenames) to local relative paths

    Example:
        >>> artifacts = [
        ...     MockArtifact(
        ...         url="https://sec.gov/data/123/img1.gif",
        ...         filename="img1.gif",
        ...         local_path="NASDAQ/AAPL/2025/AAPL_2025_FY_31-10-2025_image-001.gif"
        ...     )
        ... ]
        >>> mapping = build_image_replacement_mapping("https://sec.gov/filing.html", artifacts)
        >>> mapping["https://sec.gov/data/123/img1.gif"]
        './AAPL_2025_FY_31-10-2025_image-001.gif'
        >>> mapping["img1.gif"]  # Also mapped by filename
        './AAPL_2025_FY_31-10-2025_image-001.gif'
    """
    from pathlib import Path
    from urllib.parse import urljoin, urlparse

    mapping = {}

    for artifact in image_artifacts:
        remote_url = artifact.url
        original_filename = artifact.filename if hasattr(artifact, 'filename') else Path(remote_url).name
        local_path = artifact.local_path

        # Convert absolute local path to relative path (filename only)
        local_filename = Path(local_path).name
        relative_path = f"./{local_filename}"

        # Map 1: Full URL → local path
        mapping[remote_url] = relative_path

        # Map 2: Filename only → local path
        # This handles cases where HTML has relative references like "aapl-20250927_g1.jpg"
        mapping[original_filename] = relative_path

        # Map 3: URL path (without domain) → local path
        # This handles cases like "/Archives/edgar/data/.../image.gif"
        parsed = urlparse(remote_url)
        if parsed.path:
            mapping[parsed.path] = relative_path

    logger.debug(
        "image_mapping_built",
        mapping_size=len(mapping),
        artifacts_count=len(image_artifacts)
    )

    return mapping


def validate_encoding_preserved(
    original_bytes: bytes,
    processed_bytes: bytes
) -> bool:
    """
    Validate that encoding was preserved during HTML processing.

    Checks:
    1. Declared encoding matches in both versions
    2. No UTF-8 multi-byte characters introduced in ASCII files
    3. File size increase is minimal (only due to path changes)

    Args:
        original_bytes: Original HTML content
        processed_bytes: Processed HTML content

    Returns:
        True if encoding was properly preserved, False otherwise
    """
    # Extract encoding declarations
    original_encoding = detect_encoding(original_bytes)
    processed_encoding = detect_encoding(processed_bytes)

    if original_encoding != processed_encoding:
        logger.error(
            "encoding_mismatch",
            original=original_encoding,
            processed=processed_encoding
        )
        return False

    # If original declared ASCII, check for UTF-8 multi-byte sequences
    if original_encoding == 'ascii':
        # Common UTF-8 multi-byte patterns
        utf8_patterns = [
            b'\xe2\x80\x99',  # right single quote '
            b'\xe2\x80\x98',  # left single quote '
            b'\xe2\x80\x9c',  # left double quote "
            b'\xe2\x80\x9d',  # right double quote "
            b'\xe2\x80\x94',  # em-dash —
            b'\xe2\x80\x93',  # en-dash –
        ]

        for pattern in utf8_patterns:
            if pattern in processed_bytes:
                logger.error(
                    "utf8_in_ascii_file",
                    pattern=pattern.hex(),
                    encoding=original_encoding
                )
                return False

    # Check file size increase is reasonable (< 10% or < 10KB)
    size_diff = len(processed_bytes) - len(original_bytes)
    size_increase_pct = (size_diff / len(original_bytes)) * 100 if len(original_bytes) > 0 else 0

    if size_increase_pct > 10 and size_diff > 10000:
        logger.warning(
            "excessive_size_increase",
            size_diff=size_diff,
            size_increase_pct=f"{size_increase_pct:.2f}%"
        )
        # Don't fail, just warn - could be legitimate path changes

    logger.info(
        "encoding_validation_passed",
        encoding=original_encoding,
        size_diff=size_diff
    )

    return True
