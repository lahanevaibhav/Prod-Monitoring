import os
import re
import base64
import fnmatch
from datetime import datetime
from pathlib import Path
import argparse

# List of region directory names (subfolders under service dirs) to generate reports for.
REPORT_REGIONS = [
    "AU",
    "CA",
    "DE",
    "JP",
    "NA1",
    "UK",
]

# Services to process under perf/prod
SERVICES = ["SRA", "SRM"]

# Name of the screenshots subfolder inside each service/region directory
SCREENSHOTS_DIRNAME = "screenshots"
IMAGE_INCLUDE_NAMES = []
IMAGE_INCLUDE_PATTERNS = "*.png"

# Whether to embed images into the HTML (base64). Set to True for standalone HTML.
EMBED_IMAGES = True

# Whether to also generate PDF files (requires Playwright + chromium installed).
GENERATE_PDF = True

# Base directory root (current directory). The subdirectory is decided by is_perf (perf/prod).
BASE_DIR_ROOT = "."

# ==================================================================================

# Resolve template relative to this file so it works from any working directory.
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "report_template.html")


def humanize_title(filename: str) -> str:
    name = os.path.splitext(os.path.basename(filename))[0]
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name if name.isupper() else name.title()


def image_to_data_uri(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = "image/png" if ext == "png" else f"image/{ext}"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def group_images_by_type(image_paths):
    groups = {}
    # heuristic keywords -> group name
    mapping = {
        "errors": ("error", "fail", "exception"),
        "performance": ("perf", "latency", "duration", "response", "time", "ms"),
        "external": ("external", "api"),
    }
    for p in image_paths:
        name = os.path.basename(p).lower()
        assigned = False
        for group_name, keywords in mapping.items():
            if any(k in name for k in keywords):
                groups.setdefault(group_name.title(), []).append(p)
                assigned = True
                break
        if not assigned:
            groups.setdefault("Other", []).append(p)
    # keep deterministic order
    ordered = {}
    for key in ["Errors", "Performance", "External", "Other"]:
        if key in groups:
            ordered[key] = groups[key]
    return ordered


def build_groups_html(groups, embed, region_dir):
    """
    Build HTML for grouped plots.
    Each group is wrapped in <section class="group"> so print CSS can start groups on new pages.
    """
    groups_html = []
    sidebar_items = []
    total = 0
    for group_name, imgs in groups.items():
        total += len(imgs)
        # group header with count
        header = f'<div class="group-header">{group_name} <small style="color:var(--muted)">({len(imgs)})</small></div>'
        # grid of plots for this group
        plot_cards = []
        for idx, img_path in enumerate(sorted(imgs, key=lambda p: os.path.basename(p).lower()), start=1):
            title = humanize_title(os.path.basename(img_path))
            if embed:
                src = image_to_data_uri(img_path)
            else:
                src = os.path.relpath(img_path, region_dir).replace("\\", "/")
            img_tag = f'<img src="{src}" alt="{title}"/>'
            safe_group_id = re.sub(r'\W+', '-', group_name.lower())
            plot_cards.append(f'''
              <article class="plot" id="plot-{safe_group_id}-{idx}">
                <div class="plot-title">{title}</div>
                <div class="plot-body">{img_tag}</div>
              </article>
            ''')
        grid_html = '<div class="grid">' + "\n".join(plot_cards) + '</div>'
        safe_group_id = re.sub(r'\W+', '-', group_name.lower())
        groups_html.append(f'<section class="group" id="group-{safe_group_id}">{header}{grid_html}</section>')
        sidebar_items.append(f'<div class="group-item"><div>{group_name}</div><b>{len(imgs)}</b></div>')
    return "\n".join(groups_html), "\n".join(sidebar_items), total


def load_template():
    if not os.path.exists(TEMPLATE_PATH):
        raise SystemExit(
            f"❌ Template not found: {TEMPLATE_PATH}. "
            "Ensure src/prod_monitoring/templates/report_template.html exists."
        )
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def export_pdf_playwright(html_path: str, pdf_path: str):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright is not installed. Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium\n"
        ) from e

    file_url = Path(html_path).absolute().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.goto(file_url, wait_until="networkidle")
        # Emulate print so @page rules are respected
        page.emulate_media(media="print")
        page.wait_for_timeout(600)
        # prefer_css_page_size tells Playwright to use CSS @page size where provided
        page.pdf(path=pdf_path,
                 format="A4",
                 print_background=True,
                 margin={"top": "6mm", "bottom": "6mm", "left": "6mm", "right": "6mm"},
                 prefer_css_page_size=True)
        browser.close()


def collect_images(shots_dir, include_patterns):
    """Collect image files from shots_dir based on comma-separated patterns or a list.
    Patterns beginning with 're:' are treated as case-insensitive regular expressions.
    Other patterns are treated as shell-style globs (case-insensitive).
    Returns a sorted, deduplicated list of absolute file paths.
    """
    # normalize include_patterns into a list of strings
    if include_patterns is None:
        include_patterns = IMAGE_INCLUDE_PATTERNS
    if isinstance(include_patterns, str):
        patterns = [p.strip() for p in include_patterns.split(",") if p.strip()]
    elif isinstance(include_patterns, (list, tuple)):
        patterns = [str(p).strip() for p in include_patterns if str(p).strip()]
    else:
        raise ValueError("include_patterns must be a str or list of str")

    try:
        files = os.listdir(shots_dir)
    except OSError as e:
        # caller should handle missing directory; return empty list
        print(f"⚠️  Unable to read screenshots directory {shots_dir}: {e}")
        return []

    matches = []
    seen = set()
    for pat in patterns:
        if pat.lower().startswith("re:"):
            # regex
            regex_text = pat[3:]
            try:
                reg = re.compile(regex_text, re.IGNORECASE)
            except re.error as e:
                print(f"⚠️  Invalid regex pattern '{pat}': {e}")
                continue
            for fname in files:
                if reg.search(fname):
                    full = os.path.join(shots_dir, fname)
                    if os.path.isfile(full) and full not in seen:
                        matches.append(full)
                        seen.add(full)
        else:
            # glob-like pattern (case-insensitive)
            low_pat = pat.lower()
            for fname in files:
                if fnmatch.fnmatch(fname.lower(), low_pat):
                    full = os.path.join(shots_dir, fname)
                    if os.path.isfile(full) and full not in seen:
                        matches.append(full)
                        seen.add(full)
    # deterministic order by filename
    matches.sort(key=lambda p: os.path.basename(p).lower())
    return matches


def collect_by_exact_names(shots_dir, name_list):
    """Collect files from shots_dir that match names in name_list (case-insensitive),
    preserving the order of name_list. If a name doesn't match any file it is skipped with a warning.
    """
    try:
        files = os.listdir(shots_dir)
    except OSError as e:
        print(f"⚠️  Unable to read screenshots directory {shots_dir}: {e}")
        return []

    # map lowercased filenames to actual file paths
    file_map = {fname.lower(): os.path.join(shots_dir, fname) for fname in files if os.path.isfile(os.path.join(shots_dir, fname))}
    matches = []
    for desired in name_list:
        dn = desired.strip().lower()
        # try exact match
        if dn in file_map:
            matches.append(file_map[dn])
            continue
        # try with or without extension
        base = os.path.splitext(dn)[0]
        found = False
        for fname_lower, full in file_map.items():
            if os.path.splitext(fname_lower)[0] == base:
                matches.append(full)
                found = True
                break
        if not found:
            print(f"⚠️  Named image not found in {shots_dir}: {desired}")
    return matches


def build_env_base_dir(is_perf: bool) -> str:
    """
    Decide environment base directory under the current working directory:
    - perf mode: ./perf
    - prod mode: ./prod
    """
    sub = "perf" if is_perf else "prod"
    env_dir = os.path.join(BASE_DIR_ROOT, sub)
    return env_dir


def run_for_service_region(service: str, region: str, env_dir: str):
    """
    Run report generation for a single service (SRA/SRM) and region under the given environment directory.
    Expected structure:
      <env_dir>/<service>/<region>/screenshots/*.png
    """
    service_dir = os.path.join(env_dir, service)
    region_dir = os.path.join(service_dir, region)
    shots_dir = os.path.join(region_dir, SCREENSHOTS_DIRNAME)

    if not os.path.isdir(service_dir):
        print(f"⚠️  Service directory not found, skipping: {service_dir}")
        return
    if not os.path.isdir(region_dir):
        print(f"⚠️  Region directory not found for service '{service}', skipping: {region_dir}")
        return
    if not os.path.isdir(shots_dir):
        print(f"⚠️  Screenshots directory not found for service '{service}' region '{region}', skipping: {shots_dir}")
        return

    if IMAGE_INCLUDE_NAMES:
        images = collect_by_exact_names(shots_dir, IMAGE_INCLUDE_NAMES)
    else:
        images = collect_images(shots_dir, IMAGE_INCLUDE_PATTERNS)

    if not images:
        print(f"⚠️  No images matched configuration for {service}/{region}")
        # Continue to still create a skeleton report? Stick to original behavior: only warn.

    groups = group_images_by_type(images)
    groups_html, sidebar_html, total = build_groups_html(groups, EMBED_IMAGES, region_dir)

    out_html = os.path.join(region_dir, f"report_{region}.html")
    template = load_template()
    html = template.format(
        region=region,
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        groups_html=groups_html,
        sidebar_html=sidebar_html,
        total_plots=total,
        mode=("Embedded" if EMBED_IMAGES else "Linked"),
        embed_text=("Embedded" if EMBED_IMAGES else "Linked"),
        service=service,          # Safe even if template doesn't use it
        environment=os.path.basename(env_dir)  # perf or prod
    )

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report created: {out_html}  ({service}/{region})")
    print(f"✅ Included images: {len(images)}")

    if GENERATE_PDF:
        out_pdf = os.path.join(region_dir, f"report_{region}.pdf")
        print(f"🧾 Exporting PDF -> {out_pdf} (playwright) [{service}/{region}]")
        export_pdf_playwright(out_html, out_pdf)
        print("✅ PDF created using Playwright (Chromium).")


def main():
    parser = argparse.ArgumentParser(description="Generate region reports from perf/prod -> SRA/SRM -> regions directories.")
    parser.add_argument(
        "--is-perf",
        action="store_true",
        help="Use ./perf/... as the environment root. If not set, uses ./prod/..."
    )
    args = parser.parse_args()

    env_dir = build_env_base_dir(args.is_perf)
    print(f"📁 Environment root: {env_dir}")

    # Run for both services and all configured regions
    for service in SERVICES:
        for region in REPORT_REGIONS:
            run_for_service_region(service, region, env_dir)


if __name__ == "__main__":
    main()
