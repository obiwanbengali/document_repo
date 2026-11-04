"""Export a Pathways report page as one self-contained HTML file.

Examples:
    python -m pathways_analysis.standalone_export ent
    python -m pathways_analysis.standalone_export architecture
    python -m pathways_analysis.standalone_export --all

The exporter inlines local CSS, JavaScript, vendored Plotly and the generated report JSON.
The result can be opened directly from disk and sent as a single HTML attachment.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .config import Paths

PAGE_ALIASES = {
    "overview": "index.html",
    "estate": "phase1.html",
    "families": "phase2.html",
    "architecture": "phase3.html",
    "ent": "ent.html",
    "revised-ent": "revised-ent.html",
}

STANDALONE_LINKS = {
    "index.html": "index-standalone.html",
    "phase1.html": "phase1-standalone.html",
    "phase2.html": "phase2-standalone.html",
    "phase3.html": "phase3-standalone.html",
    "ent.html": "ent-standalone.html",
    "revised-ent.html": "revised-ent-standalone.html",
}

SCRIPT_RE = re.compile(r'<script\s+src="([^"]+)"\s*></script>', re.IGNORECASE)
STYLE_RE = re.compile(r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*/?>', re.IGNORECASE)
LOAD_REPORT_RE = re.compile(r"loadReport\(\s*['\"]([^'\"]+\.json)['\"]")


def _safe_script_text(text: str) -> str:
    return text.replace("</script", "<\\/script")


def _inline_styles(html: str, reports: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        path = reports / href
        if not path.is_file():
            raise FileNotFoundError(f"Stylesheet not found: {path}")
        return "<style>\n" + path.read_text(encoding="utf-8") + "\n</style>"
    return STYLE_RE.sub(replace, html)


def _collect_data_filenames(html: str, reports: Path) -> set[str]:
    names: set[str] = set()
    for src in SCRIPT_RE.findall(html):
        path = reports / src
        if path.is_file() and path.suffix.lower() == ".js":
            names.update(LOAD_REPORT_RE.findall(path.read_text(encoding="utf-8")))
    return names


def _embedded_data_script(html: str, reports: Path) -> str:
    payloads = {}
    for filename in sorted(_collect_data_filenames(html, reports)):
        path = reports / "data" / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"Report data not found: {path}. Generate the report data first."
            )
        payloads[filename] = json.loads(path.read_text(encoding="utf-8"))
    serialised = json.dumps(payloads, ensure_ascii=False).replace("</", "<\\/")
    return f"<script>window.__PATHWAYS_STANDALONE_DATA__ = {serialised};</script>"


def _rewrite_navigation(html: str) -> str:
    """Point report navigation at neighbouring standalone exports."""
    for source, target in STANDALONE_LINKS.items():
        html = html.replace(f'href="{source}"', f'href="{target}"')
    return html


def _inline_scripts(html: str, reports: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        src = match.group(1)
        path = reports / src
        if not path.is_file():
            raise FileNotFoundError(f"Script not found: {path}")
        content = _safe_script_text(path.read_text(encoding="utf-8"))
        return f"<script>\n/* inlined from {src} */\n{content}\n</script>"
    return SCRIPT_RE.sub(replace, html)


def export_page(page: str, output: Path | None = None) -> Path:
    paths = Paths.discover()
    reports = paths.reports
    filename = PAGE_ALIASES.get(page, page)
    if not filename.endswith(".html"):
        filename += ".html"

    source = reports / filename
    if not source.is_file():
        raise FileNotFoundError(f"Report page not found: {source}")

    html = source.read_text(encoding="utf-8")
    embedded_data = _embedded_data_script(html, reports)
    html = _inline_styles(html, reports)
    html = _rewrite_navigation(html)
    html = html.replace("</head>", (
        "<style>.standalone-note{padding:.65rem 1rem;background:#f4f4f1;"
        "border-bottom:1px solid #e1e0d9;font-size:.85rem}</style></head>"
    ))
    html = html.replace("<body>", (
        "<body><div class=\"standalone-note\"><strong>Standalone copy.</strong> "
        "All report data and assets are embedded in this file. Navigation links open "
        "neighbouring standalone report files when they are kept in the same folder."
        "</div>"
    ))
    # Data must exist before common.js and page-specific JS execute.
    first_script = html.find("<script")
    if first_script >= 0:
        html = html[:first_script] + embedded_data + "\n" + html[first_script:]
    else:
        html = html.replace("</body>", embedded_data + "\n</body>")
    html = _inline_scripts(html, reports)

    if output is None:
        out_dir = paths.project_root / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        output = out_dir / f"{source.stem}-standalone.html"
    else:
        output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(html, encoding="utf-8")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export report pages as standalone HTML.")
    parser.add_argument("page", nargs="?", choices=sorted(PAGE_ALIASES), help="Report to export.")
    parser.add_argument("--all", action="store_true", help="Export every report page.")
    parser.add_argument("--output", type=Path, help="Output path for a single page.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.all:
        if args.output:
            raise SystemExit("--output cannot be combined with --all")
        for alias in PAGE_ALIASES:
            print(f"Wrote {export_page(alias)}")
        return 0
    if not args.page:
        raise SystemExit("Specify a page (overview, estate, families, architecture, ent, revised-ent) or --all")
    print(f"Wrote {export_page(args.page, args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
