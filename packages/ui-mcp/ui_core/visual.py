"""In-memory bounded PNG/JPEG comparison, without network/filesystem access.

Grid-region grouping adapted from Replica imgdiff.py (_regions), MIT,
Copyright (c) 2026 Jake Schincariol; see docs/REPLICA_LICENSE.txt.
Image decoding and comparison are independently implemented with Pillow.
"""
from __future__ import annotations

import base64
import binascii
from io import BytesIO
import math
import struct
import threading
from typing import Any

from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError

MAX_IMAGE_BYTES = 180_000  # two base64 strings + RPC envelope fit 512000 bytes
MAX_PIXELS, MAX_SIDE = 2_000_000, 4096
_SLOT = threading.BoundedSemaphore(1)


def _decode(value: str) -> Image.Image:
    if not isinstance(value, str) or not value or len(value) > 240_000:
        raise ValueError('Image must be raw base64, at most 180000 decoded bytes')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('Image is not valid raw base64') from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError('Encoded image size limit exceeded')
    png = raw.startswith(b'\x89PNG\r\n\x1a\n')
    if not png and not raw.startswith(b'\xff\xd8\xff'):
        raise ValueError('Only PNG and JPEG images are accepted')
    if png:
        # Refuse compressed ancillary metadata and animation before decoder use.
        pos = 8
        while pos < len(raw):
            if pos + 12 > len(raw):
                raise ValueError('Truncated PNG chunk')
            size = struct.unpack('>I', raw[pos:pos + 4])[0]
            kind = raw[pos + 4:pos + 8]
            if size > len(raw) - pos - 12:
                raise ValueError('Invalid PNG chunk length')
            if kind in (b'zTXt', b'iTXt', b'iCCP', b'acTL', b'fdAT'):
                raise ValueError('Compressed PNG metadata and animation are unsupported')
            pos += size + 12
    try:
        with Image.open(BytesIO(raw), formats=('PNG', 'JPEG')) as img:
            w, h = img.size
            if min(w, h) < 1 or max(w, h) > MAX_SIDE or w * h > MAX_PIXELS:
                raise ValueError('Decoded image exceeds 4096 side or 2000000 pixel limit')
            if getattr(img, 'n_frames', 1) != 1:
                raise ValueError('Animated images are unsupported')
            img.verify()
        with Image.open(BytesIO(raw), formats=('PNG', 'JPEG')) as img:
            img.load()
            rgba = img.convert('RGBA')
            white = Image.new('RGBA', img.size, 'white')
            return Image.alpha_composite(white, rgba).convert('RGB')
    except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Image is corrupt or unsafe to decode') from exc


def _regions(flags, n_rows, n_cols):
    """Four-connected grid components; adapted from Replica imgdiff._regions."""
    seen, regions = set(), []
    for r in range(n_rows):
        for c in range(n_cols):
            if not flags[r][c] or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                cr, cc = stack.pop()
                cells.append((cr, cc))
                for nr, nc in ((cr + 1, cc), (cr - 1, cc), (cr, cc + 1), (cr, cc - 1)):
                    if 0 <= nr < n_rows and 0 <= nc < n_cols and flags[nr][nc] and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            rs, cs = [x[0] for x in cells], [x[1] for x in cells]
            regions.append((min(rs), min(cs), max(rs), max(cs), len(cells)))
    return sorted(regions, key=lambda t: -t[4])


def _edges(im):
    # Per-channel maximum detects chromatic boundaries, including equal luminance.
    channels = [c.filter(ImageFilter.FIND_EDGES) for c in im.split()]
    e = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    e = e.point(lambda p: 255 if p > 32 else 0)
    # FIND_EDGES leaves image borders unchanged; do not score those artificial edges.
    w, h = e.size
    e.paste(0, (0, 0, w, 1)); e.paste(0, (0, h - 1, w, h))
    e.paste(0, (0, 0, 1, h)); e.paste(0, (w - 1, 0, w, h))
    return e


def _hits(mask):
    return sum(mask.histogram()[1:])


def compare(reference_image: str, candidate_image: str, comparison_mode: str = 'layout',
            viewport: str = 'unspecified', tolerance: int = 24,
            same_state: bool = False) -> dict[str, Any]:
    if comparison_mode not in ('layout', 'pixel', 'region'):
        raise ValueError('comparison_mode must be layout, pixel or region')
    if viewport not in ('mobile', 'tablet', 'desktop', 'unspecified'):
        raise ValueError('Invalid viewport category')
    if type(tolerance) is not int or not 0 <= tolerance <= 64 or type(same_state) is not bool:
        raise ValueError('tolerance must be an integer 0..64; same_state must be boolean')
    if not _SLOT.acquire(blocking=False):
        raise ValueError('Visual comparison busy; retry after the current call completes')
    try:
        return _compare(reference_image, candidate_image, comparison_mode, viewport, tolerance, same_state)
    finally:
        _SLOT.release()


def _compare(reference_image, candidate_image, mode, viewport, tolerance, same_state):
    a, b = _decode(reference_image), _decode(candidate_image)
    mismatch = a.size != b.size
    result = {'analysis_version': '0.4', 'comparison_mode': mode,
              'viewport': {'category': viewport, 'reference': {'width': a.width, 'height': a.height},
                           'candidate': {'width': b.width, 'height': b.height},
                           'reference_aspect_ratio': round(a.width / a.height, 6),
                           'candidate_aspect_ratio': round(b.width / b.height, 6)},
              'layout_similarity': None, 'pixel_difference': None, 'changed_regions': [],
              'dimension_mismatch': mismatch, 'diff_artifact': None,
              'warnings': ['Image metrics do not certify UX, accessibility or functional completeness'],
              'evidence': {'state_match': 'caller_asserted' if same_state else 'unverified',
                           'alignment': 'exact dimensions; no resize or crop', 'tolerance': tolerance,
                           'coordinate_space': 'image pixels (not CSS pixels)',
                           'alpha_background': 'white', 'exif_orientation': 'not_applied'},
              'status': 'INCOMPARABLE' if mismatch else 'COMPARED', 'release_authorized': False}
    if not same_state:
        result['warnings'].append('Screen state, DPR, font and capture timing are unverified; differences may be conditional')
    if mismatch:
        result['warnings'].append('Dimensions differ; no partial image was silently scored. Recapture with matching viewport/DPR')
        result['layout_change_summary'] = 'Comparison withheld because image dimensions differ'
        return result
    w, h = a.size
    channels = ImageChops.difference(a, b).split()
    delta = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    pixel_mask = delta.point(lambda p: 255 if p > tolerance else 0)
    pixel_hits = _hits(pixel_mask)
    ea, eb = _edges(a), _edges(b)
    # Symmetric tolerant edge overlap, not density alone: same-cell moves are visible.
    missing = ImageChops.subtract(ea, eb.filter(ImageFilter.MaxFilter(3)))
    added = ImageChops.subtract(eb, ea.filter(ImageFilter.MaxFilter(3)))
    edge_mask = ImageChops.lighter(missing, added)
    edge_count = _hits(ea) + _hits(eb)
    similarity = 1 - (_hits(missing) + _hits(added)) / edge_count if edge_count else None
    result['layout_similarity'] = round(similarity, 6) if similarity is not None else None
    result['pixel_difference'] = {'ratio': round(pixel_hits / (w * h), 6), 'changed_pixels': pixel_hits,
                                  'total_pixels': w * h}
    result['evidence'].update({'edge_pixels': edge_count, 'edge_threshold': 32, 'edge_tolerance_pixels': 1})
    if not edge_count:
        result['warnings'].append('No structural edges; layout similarity is unknown, not perfect')
    mask = edge_mask if mode == 'layout' else pixel_mask if mode == 'pixel' else ImageChops.lighter(edge_mask, pixel_mask)
    cell_w, cell_h = max(1, math.ceil(w / 16)), max(1, math.ceil(h / 16))
    cols, rows = math.ceil(w / cell_w), math.ceil(h / cell_h)
    flags = [[bool(mask.crop((c * cell_w, r * cell_h, min(w, (c + 1) * cell_w),
                              min(h, (r + 1) * cell_h))).getbbox()) for c in range(cols)] for r in range(rows)]
    result['changed_regions'] = [{'x': c0 * cell_w, 'y': r0 * cell_h,
                                  'width': min(w, (c1 + 1) * cell_w) - c0 * cell_w,
                                  'height': min(h, (r1 + 1) * cell_h) - r0 * cell_h,
                                  'cells': cells, 'basis': 'coarse connected difference tiles',
                                  'possible_cause': 'layout, missing content or capture-state difference; not semantically classified'}
                                 for r0, c0, r1, c1, cells in _regions(flags, rows, cols)]
    out = BytesIO()
    # Mask retains difference geometry (potentially sensitive); caller decides retention.
    mask.convert('1').save(out, format='PNG', optimize=False)
    result['diff_artifact'] = {'mime_type': 'image/png', 'encoding': 'base64',
                               'data': base64.b64encode(out.getvalue()).decode('ascii'),
                               'kind': 'binary_difference_mask', 'stored': False, 'width': w, 'height': h}
    result['layout_change_summary'] = str(len(result['changed_regions'])) + ' changed coarse regions in ' + mode + ' mode'
    return result
