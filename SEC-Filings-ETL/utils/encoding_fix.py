"""
Phase 1: HTML Encoding Fix Module

Normalizes HTML files to UTF-8, inserts <meta charset="utf-8">, and cleans mojibake.
Does NOT modify images or image references (that's Phase 2).
"""
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog

from bs4 import BeautifulSoup
import chardet

logger = structlog.get_logger()


# Common mojibake patterns (UTF-8 bytes mis-interpreted as Latin-1/CP1252)
# Using Unicode escape sequences to avoid syntax errors
MOJIBAKE_PATTERNS = {
    '\u00e2\u0080\u0099': '\u2019',  # â€™ → ' (right single quote)
    '\u00e2\u0080\u009c': '\u201c',  # â€œ → " (left double quote)
    '\u00e2\u0080\u009d': '\u201d',  # â€ → " (right double quote)
    '\u00e2\u0080\u0094': '\u2014',  # â€" → — (em dash)
    '\u00e2\u0080\u0093': '\u2013',  # â€" → – (en dash)
    '\u00e2\u0080\u00a6': '\u2026',  # â€¦ → … (horizontal ellipsis)
    '\u00c2\u00a0': ' ',             # Â  → space (non-breaking space mojibake)
    '\u00c3\u00a9': '\u00e9',       # Ã© → é (e with acute)
    '\u00c3\u00a8': '\u00e8',       # Ã¨ → è (e with grave)
    '\u00c3\u00a1': '\u00e1',       # Ã¡ → á (a with acute)
}


def detect_encoding(content_bytes: bytes) -> str:
    """
    Detect encoding of HTML content using multiple strategies.

    Priority:
    1. Check HTML meta charset tag
    2. Check XML declaration
    3. Use chardet library
    4. Default to UTF-8

    Args:
        content_bytes: Raw bytes of HTML content

    Returns:
        Detected encoding string (e.g., 'utf-8', 'latin-1', 'ascii')
    """
    # Strategy 1: Check meta charset in HTML
    try:
        # Look in first 2KB for meta charset
        header = content_bytes[:2048]
        header_str = header.decode('ascii', errors='ignore')

        # HTML5 style: <meta charset="...">
        match = re.search(r'<meta\s+charset=["\']?([^"\'>\s]+)["\']?', header_str, re.IGNORECASE)
        if match:
            declared = match.group(1).lower()
            if 'utf' in declared:
                return 'utf-8'
            elif 'ascii' in declared:
                return 'ascii'
            elif 'iso-8859' in declared or 'latin' in declared:
                return 'latin-1'
            return declared

        # HTML4 style: <meta http-equiv="Content-Type" content="text/html; charset=...">
        match = re.search(r'<meta\s+http-equiv=["\']?content-type["\']?\s+content=["\']text/html;\s*charset=([^"\'>\s]+)["\']?',
                         header_str, re.IGNORECASE)
        if match:
            declared = match.group(1).lower()
            if 'utf' in declared:
                return 'utf-8'
            elif 'ascii' in declared:
                return 'ascii'
            elif 'iso-8859' in declared or 'latin' in declared:
                return 'latin-1'
            return declared

    except Exception as e:
        logger.debug("meta_charset_detection_failed", error=str(e))

    # Strategy 2: Check XML declaration
    try:
        if content_bytes.startswith(b'<?xml'):
            header = content_bytes[:500]
            match = re.search(rb"encoding=['\"]([^'\"]+)['\"]", header)
            if match:
                declared = match.group(1).decode('ascii').lower()
                if 'utf' in declared:
                    return 'utf-8'
                elif 'ascii' in declared:
                    return 'ascii'
                elif 'iso-8859' in declared or 'latin' in declared:
                    return 'latin-1'
                return declared
    except Exception as e:
        logger.debug("xml_declaration_detection_failed", error=str(e))

    # Strategy 3: Use chardet
    try:
        detection = chardet.detect(content_bytes[:10000])  # Sample first 10KB
        if detection and detection.get('confidence', 0) > 0.7:
            encoding = detection['encoding'].lower()
            # Normalize encoding names
            if 'utf' in encoding or 'utf8' in encoding:
                return 'utf-8'
            elif 'ascii' in encoding:
                return 'ascii'
            elif 'iso-8859' in encoding or 'latin' in encoding:
                return 'latin-1'
            return encoding
    except Exception as e:
        logger.debug("chardet_detection_failed", error=str(e))

    # Default
    return 'utf-8'


def detect_mojibake(content_bytes: bytes) -> Tuple[bool, List[str]]:
    """
    Detect common mojibake patterns in content.

    Args:
        content_bytes: Raw bytes of HTML content

    Returns:
        Tuple of (has_mojibake, list of found patterns)
    """
    found_patterns = []

    # Try to decode as UTF-8 first to check for valid UTF-8
    try:
        content_str = content_bytes.decode('utf-8')

        # Check for mojibake patterns (these are typically UTF-8 glyphs that look wrong)
        for pattern in MOJIBAKE_PATTERNS.keys():
            if pattern in content_str:
                found_patterns.append(pattern)

    except UnicodeDecodeError:
        # If it can't decode as UTF-8, it's likely wrong encoding
        pass

    return (len(found_patterns) > 0, found_patterns)


def clean_mojibake(content_str: str) -> str:
    """
    Clean common mojibake patterns from string.

    Args:
        content_str: String content with potential mojibake

    Returns:
        Cleaned string
    """
    result = content_str

    for mojibake, correct in MOJIBAKE_PATTERNS.items():
        if mojibake in result:
            result = result.replace(mojibake, correct)
            logger.debug("mojibake_cleaned", pattern=mojibake, replacement=correct)

    return result


def insert_meta_charset(html_str: str) -> str:
    """
    Insert or update <meta charset="utf-8"> in HTML <head> using regex.

    CRITICAL: Uses regex instead of BeautifulSoup to preserve:
    - HTML entities (&#160;, &#8217;, etc.) - NO conversion to Unicode
    - Tag case sensitivity (<ix:nonNumeric> NOT <ix:nonnumeric>)
    - Inline XBRL structure - exact preservation
    - XML namespaces - no attribute reordering

    Rules:
    - If <meta charset="utf-8"> already exists, do nothing
    - If <meta charset> exists with wrong value, update it
    - If missing, insert right after <head> tag
    - Preserve ALL other content byte-for-byte

    Args:
        html_str: HTML content as string

    Returns:
        Updated HTML string with <meta charset="utf-8">
    """
    # Check if <meta charset="utf-8"> already exists (case insensitive)
    if re.search(r'<meta\s+charset=["\']?utf-8["\']?', html_str, re.IGNORECASE):
        logger.debug("meta_charset_already_correct")
        return html_str

    # Check for existing <meta charset="..."> with wrong encoding
    # Match: <meta charset="anything-but-utf-8" /> or <meta charset='...' />
    wrong_charset_match = re.search(
        r'<meta\s+charset=["\']?(?!utf-8\b)([^"\'>\s]+)["\']?\s*/?>',
        html_str,
        re.IGNORECASE
    )

    if wrong_charset_match:
        # Replace wrong charset with utf-8
        old_meta = wrong_charset_match.group(0)
        new_meta = '<meta charset="utf-8"/>'
        html_str = html_str.replace(old_meta, new_meta, 1)
        logger.debug("meta_charset_replaced", old=wrong_charset_match.group(1))
        return html_str

    # Check for old-style Content-Type meta and remove it
    old_style_pattern = r'<meta\s+http-equiv=["\']?content-type["\']?\s+content=["\']text/html;\s*charset=[^"\']+["\']?\s*/?>'
    if re.search(old_style_pattern, html_str, re.IGNORECASE):
        html_str = re.sub(old_style_pattern, '', html_str, count=1, flags=re.IGNORECASE)
        logger.debug("old_style_meta_removed")

    # Find <head> tag and insert <meta charset="utf-8"/> right after it
    head_match = re.search(r'(<head[^>]*>)', html_str, re.IGNORECASE)

    if head_match:
        # Insert right after <head> tag
        insert_pos = head_match.end()
        html_str = (
            html_str[:insert_pos] +
            '<meta charset="utf-8"/>\n' +
            html_str[insert_pos:]
        )
        logger.debug("meta_charset_inserted_after_head")
    else:
        # No <head> tag found - try to insert after <html> tag
        html_match = re.search(r'(<html[^>]*>)', html_str, re.IGNORECASE)

        if html_match:
            insert_pos = html_match.end()
            html_str = (
                html_str[:insert_pos] +
                '\n<head><meta charset="utf-8"/></head>\n' +
                html_str[insert_pos:]
            )
            logger.debug("meta_charset_inserted_with_new_head")
        else:
            # No <html> tag either - prepend to document (after XML declaration if present)
            # Check for XML declaration
            xml_match = re.match(r'(<\?xml[^>]*\?>)', html_str, re.IGNORECASE)
            if xml_match:
                insert_pos = xml_match.end()
                html_str = (
                    html_str[:insert_pos] +
                    '\n<meta charset="utf-8"/>\n' +
                    html_str[insert_pos:]
                )
                logger.debug("meta_charset_inserted_after_xml")
            else:
                html_str = '<meta charset="utf-8"/>\n' + html_str
                logger.debug("meta_charset_prepended")

    return html_str


def fix_xml_declaration(html_str: str) -> str:
    """
    Fix or remove XML declaration with wrong encoding.

    Args:
        html_str: HTML content

    Returns:
        HTML with corrected XML declaration
    """
    # Remove or update XML declarations with wrong encoding
    if html_str.strip().startswith('<?xml'):
        # Update encoding to UTF-8
        html_str = re.sub(
            r'<\?xml\s+version=["\']1\.0["\']\s+encoding=["\'][^"\']+["\']\s*\?>',
            '<?xml version="1.0" encoding="UTF-8"?>',
            html_str,
            flags=re.IGNORECASE
        )

        # Or remove if it causes issues
        # html_str = re.sub(r'<\?xml[^>]*\?>\s*', '', html_str, flags=re.IGNORECASE)

    return html_str


def fix_html_encoding(content_bytes: bytes) -> bytes:
    """
    Main function to fix HTML encoding.

    Steps:
    1. Detect current encoding
    2. Decode to string
    3. Clean mojibake patterns
    4. Insert/update <meta charset="utf-8">
    5. Fix XML declaration if present
    6. Encode back to UTF-8

    Args:
        content_bytes: Raw HTML content as bytes

    Returns:
        Fixed HTML content as UTF-8 bytes
    """
    # Detect current encoding
    detected_encoding = detect_encoding(content_bytes)

    logger.debug("encoding_detected", encoding=detected_encoding, size=len(content_bytes))

    # Decode to string
    try:
        content_str = content_bytes.decode(detected_encoding, errors='replace')
    except (UnicodeDecodeError, LookupError) as e:
        logger.warning("decode_failed", encoding=detected_encoding, error=str(e))
        # Fallback to UTF-8 with replace
        content_str = content_bytes.decode('utf-8', errors='replace')

    # Clean mojibake
    content_str = clean_mojibake(content_str)

    # Fix XML declaration
    content_str = fix_xml_declaration(content_str)

    # Insert/update meta charset
    content_str = insert_meta_charset(content_str)

    # Encode back to UTF-8
    result_bytes = content_str.encode('utf-8', errors='replace')

    return result_bytes


class EncodingFixProcessor:
    """
    Batch processor for encoding fixes with idempotence tracking.
    """

    def __init__(self, storage_root: Path, backup: bool = True):
        """
        Initialize processor.

        Args:
            storage_root: Root directory for HTML files
            backup: Whether to create .bak files before overwriting
        """
        self.storage_root = Path(storage_root)
        self.backup = backup
        self.fixed_files_db = {}  # Simple in-memory tracking (could be DB or JSON file)

        logger.info("encoding_processor_initialized", root=str(self.storage_root), backup=backup)

    def _compute_file_hash(self, content: bytes) -> str:
        """Compute SHA256 hash of file content for change detection."""
        return hashlib.sha256(content).hexdigest()[:16]

    def _needs_fixing(self, file_path: Path, content_bytes: bytes) -> Tuple[bool, str]:
        """
        Check if file needs fixing.

        Returns:
            Tuple of (needs_fixing, reason)
        """
        # Check if already processed
        file_key = str(file_path.relative_to(self.storage_root))
        if file_key in self.fixed_files_db:
            prev_hash = self.fixed_files_db[file_key].get('hash')
            current_hash = self._compute_file_hash(content_bytes)
            if prev_hash == current_hash:
                return (False, 'already_fixed')

        # Check for UTF-8 encoding and meta charset
        try:
            content_str = content_bytes.decode('utf-8')

            # Check for meta charset
            if '<meta charset="utf-8"' not in content_str and '<meta charset=\'utf-8\'' not in content_str:
                return (True, 'missing_meta_charset')

            # Check for mojibake
            has_mojibake, patterns = detect_mojibake(content_bytes)
            if has_mojibake:
                return (True, f'mojibake_found:{len(patterns)}')

            # Check encoding declaration in XML
            if content_str.strip().startswith('<?xml'):
                if 'encoding' in content_str[:200]:
                    if 'UTF-8' not in content_str[:200] and 'utf-8' not in content_str[:200]:
                        return (True, 'wrong_xml_encoding')

            return (False, 'already_correct')

        except UnicodeDecodeError:
            return (True, 'not_utf8')

    def process_file(self, file_path: Path) -> Dict:
        """
        Process a single HTML file.

        Returns:
            Dict with processing results
        """
        start_time = datetime.now()

        result = {
            'file': str(file_path.relative_to(self.storage_root)),
            'success': False,
            'skipped': False,
            'fixed': False,
            'mojibake_found': False,
            'actions': [],
            'error': None,
            'took_ms': 0
        }

        try:
            # Read file
            with open(file_path, 'rb') as f:
                original_bytes = f.read()

            original_size = len(original_bytes)
            result['original_size'] = original_size

            # Check if needs fixing
            needs_fix, reason = self._needs_fixing(file_path, original_bytes)

            if not needs_fix:
                result['skipped'] = True
                result['skip_reason'] = reason
                result['success'] = True
                return result

            result['actions'].append(reason)

            # Detect mojibake before fixing
            has_mojibake, patterns = detect_mojibake(original_bytes)
            result['mojibake_found'] = has_mojibake
            if has_mojibake:
                result['mojibake_patterns'] = patterns[:5]  # Limit to first 5

            # Fix encoding
            fixed_bytes = fix_html_encoding(original_bytes)

            # Backup if requested
            if self.backup:
                backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                if not backup_path.exists():
                    with open(backup_path, 'wb') as f:
                        f.write(original_bytes)
                    result['actions'].append('backup_created')

            # Atomic write
            temp_path = file_path.with_suffix('.tmp')
            with open(temp_path, 'wb') as f:
                f.write(fixed_bytes)

            # Replace original
            temp_path.replace(file_path)

            result['fixed'] = True
            result['new_size'] = len(fixed_bytes)
            result['size_diff'] = len(fixed_bytes) - original_size
            result['success'] = True

            # Update tracking
            file_key = str(file_path.relative_to(self.storage_root))
            self.fixed_files_db[file_key] = {
                'hash': self._compute_file_hash(fixed_bytes),
                'fixed_at': datetime.now().isoformat(),
                'actions': result['actions']
            }

            logger.info(
                "file_fixed",
                file=result['file'],
                actions=result['actions'],
                size_diff=result['size_diff']
            )

        except Exception as e:
            result['error'] = str(e)
            logger.error("file_processing_failed", file=str(file_path), error=str(e))

        finally:
            result['took_ms'] = int((datetime.now() - start_time).total_seconds() * 1000)

        return result

    def process_batch(
        self,
        file_paths: List[Path],
        max_workers: int = 8
    ) -> List[Dict]:
        """
        Process a batch of files with concurrency.

        Args:
            file_paths: List of file paths to process
            max_workers: Number of concurrent workers

        Returns:
            List of result dictionaries
        """
        results = []

        logger.info("batch_processing_started", files=len(file_paths), workers=max_workers)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self.process_file, path): path
                for path in file_paths
            }

            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error("future_failed", file=str(path), error=str(e))
                    results.append({
                        'file': str(path.relative_to(self.storage_root)),
                        'success': False,
                        'error': str(e)
                    })

        logger.info("batch_processing_completed", files=len(results))

        return results
