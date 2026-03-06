#!/usr/bin/env python3
"""
Extract figures from academic papers.

Supports two strategies:
1. arxiv HTML (preferred): Downloads complete rendered figures from arxiv HTML
2. PDF fallback: Extracts embedded images from PDF using PyMuPDF

Usage:
    # From arxiv (preferred — gets complete figures, not image fragments)
    python extract_figures.py --arxiv 2602.09401 --output /tmp/figures/

    # From PDF (fallback for non-arxiv papers)
    python extract_figures.py --pdf /path/to/paper.pdf --output /tmp/figures/

Output: figure-1.png, figure-2.png, etc. + manifest.json
"""

import sys
import os
import json
import re
import urllib.request
import urllib.error


def extract_from_arxiv_html(arxiv_id: str, output_dir: str):
    """Download figures from arxiv HTML version.

    arxiv HTML renders complete figures (architecture diagrams, charts, etc.)
    as individual image files named x1.png, x2.png, etc. This gives much
    better results than extracting from PDF, which often fragments composite
    figures into individual embedded images.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Normalize arxiv ID
    arxiv_id_clean = re.sub(r'v\d+$', '', arxiv_id)

    base_urls = [
        f"https://arxiv.org/html/{arxiv_id_clean}v1",
        f"https://arxiv.org/html/{arxiv_id_clean}",
    ]

    figures = []
    fig_count = 0

    for base_url in base_urls:
        for i in range(1, 31):
            found = False
            for ext in ["png", "jpg", "jpeg"]:
                url = f"{base_url}/x{i}.{ext}"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    response = urllib.request.urlopen(req, timeout=10)
                    image_bytes = response.read()

                    if len(image_bytes) < 1000:
                        continue

                    fig_count += 1
                    filename = f"figure-{fig_count}.{ext}"
                    filepath = os.path.join(output_dir, filename)

                    with open(filepath, "wb") as f:
                        f.write(image_bytes)

                    figures.append({
                        "index": fig_count,
                        "filename": filename,
                        "source_url": url,
                        "size_kb": round(len(image_bytes) / 1024, 1),
                    })
                    found = True
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, Exception):
                    continue

            # If we've found figures before but this index has none, we've
            # likely reached the end. Allow 2 consecutive misses before stopping.
            if not found and fig_count > 0:
                # Try one more index before giving up
                next_found = False
                for ext in ["png", "jpg", "jpeg"]:
                    url = f"{base_url}/x{i+1}.{ext}"
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        response = urllib.request.urlopen(req, timeout=5)
                        if len(response.read()) > 1000:
                            next_found = True
                    except Exception:
                        pass
                if not next_found:
                    break

        if fig_count > 0:
            break

    manifest = {"total": fig_count, "source": "arxiv_html", "figures": figures}
    print(json.dumps(manifest, indent=2))

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def extract_from_pdf(pdf_path: str, output_dir: str, min_size: int = 5000):
    """Extract embedded images from PDF using PyMuPDF.

    Note: PDF extraction pulls raw embedded images, which may be fragments
    of composite figures (e.g., individual photos within a figure grid).
    For arxiv papers, prefer extract_from_arxiv_html() which gets complete
    rendered figures. Use this for non-arxiv PDFs.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: pip install PyMuPDF --break-system-packages")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    figures = []
    seen_xrefs = set()
    fig_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            image_bytes = base_image["image"]
            if len(image_bytes) < min_size:
                continue

            ext = base_image.get("ext", "png")
            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            fig_count += 1
            filename = f"figure-{fig_count}.{ext}"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            figures.append({
                "index": fig_count,
                "filename": filename,
                "page": page_num + 1,
                "width": width,
                "height": height,
                "size_kb": round(len(image_bytes) / 1024, 1),
            })

    doc.close()

    manifest = {"total": fig_count, "source": "pdf_extraction", "figures": figures}
    print(json.dumps(manifest, indent=2))

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract figures from academic papers")
    parser.add_argument("--arxiv", help="arxiv paper ID (e.g., 2602.09401)")
    parser.add_argument("--pdf", help="Path to PDF file")
    parser.add_argument("--output", required=True, help="Output directory for figures")
    parser.add_argument("--min-size", type=int, default=5000,
                        help="Min image size in bytes for PDF mode (default: 5000)")

    args = parser.parse_args()

    if args.arxiv:
        extract_from_arxiv_html(args.arxiv, args.output)
    elif args.pdf:
        extract_from_pdf(args.pdf, args.output, args.min_size)
    else:
        print("ERROR: Provide either --arxiv <id> or --pdf <path>")
        sys.exit(1)
