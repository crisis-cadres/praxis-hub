#!/usr/bin/env python3
"""Generate the Crisis Cadres wiki markdown pages.

The wiki's content lives as committed markdown pages under docs/ (each page
editable in-browser via its "Edit this page" link). Sub-directories are fully
supported: any .md file anywhere under docs/ is normalized with the discussion
footer, and the mkdocs navigation is regenerated from the directory structure
(a folder becomes a sidebar section containing its pages).

This script:
  1. normalizes every page — strips any stale footer and re-appends the
     discussion footer ("Start a discussion" / "View discussions" /
     "Edit this page"),
  2. regenerates the homepage (index.md) from the top-level section pages,
  3. regenerates the nav in mkdocs.yml from the docs tree.

Usage:
    python wiki/generate.py
"""

import os
import urllib.parse

import yaml

REPO = "crisis-cadres/praxis-hub"
ISSUES_URL = f"https://github.com/{REPO}/issues"
FOOTER_START = "\n---\n\n**[Start a discussion]("

# Top-level pages that get their own wiki page but are excluded from the
# assembled homepage (e.g. "The Authors").
HOME_EXCLUDED = {"salish-sea-cadre"}

# Pages to keep in docs/ (with footers) but hide from the sidebar nav for now.
# Remove a slug from this set to reveal the page again.
NAV_EXCLUDED = {"production/energy"}


def footer(title, rel_path):
    quoted_title = urllib.parse.quote(title)
    return (
        "\n\n---\n\n"
        f"**[Start a discussion]({ISSUES_URL}/new?title={quoted_title})**"
        f" · [View discussions]({ISSUES_URL})"
        f" · [Edit this page](https://github.com/{REPO}/edit/main/wiki/docs/{rel_path}.md)\n"
    )


def strip_footer(content):
    idx = content.rfind(FOOTER_START)
    if idx != -1:
        return content[:idx].rstrip() + "\n"
    return content


def parse_page(path):
    with open(path) as fh:
        content = fh.read()
    clean = strip_footer(content)
    lines = clean.splitlines()
    title = lines[0].lstrip("#").strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def collect_pages(docs_dir):
    pages = []
    for root, dirs, files in os.walk(docs_dir):
        dirs.sort()
        for filename in sorted(files):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(root, filename)
            rel_path = os.path.relpath(path, docs_dir)
            if rel_path == "index.md":
                continue
            title, body = parse_page(path)
            pages.append(
                {
                    "rel_path": rel_path[: -len(".md")],
                    "title": title,
                    "body": body,
                }
            )
    return pages


def build_index(pages):
    lines = ["# Crisis Cadres\n"]
    for page in pages:
        lines.append(f"## [{page['title']}]({page['rel_path']}.md)\n")
        lines.append(page["body"])
        lines.append("")
    return "\n".join(lines).rstrip() + footer("Crisis Cadres", "index")


def build_nav(pages):
    nav = [{"Home": "index.md"}]

    top_level = [p for p in pages if "/" not in p["rel_path"]]
    regular = [p for p in top_level if p["rel_path"] not in HOME_EXCLUDED]
    excluded = [p for p in top_level if p["rel_path"] in HOME_EXCLUDED]
    for page in regular + excluded:
        nav.append({page["title"]: page["rel_path"] + ".md"})

    nested = [p for p in pages if "/" in p["rel_path"] and p["rel_path"] not in NAV_EXCLUDED]
    by_dir = {}
    for page in nested:
        by_dir.setdefault(os.path.dirname(page["rel_path"]), []).append(page)
    for directory in sorted(by_dir):
        section_title = directory.replace("-", " ").title()
        items = [{p["title"]: p["rel_path"] + ".md"} for p in by_dir[directory]]
        nav.append({section_title: items})

    return nav


def main():
    wiki_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(wiki_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    pages = collect_pages(docs_dir)
    for page in pages:
        path = os.path.join(docs_dir, page["rel_path"] + ".md")
        with open(path, "w") as fh:
            fh.write(f"# {page['title']}\n\n{page['body']}{footer(page['title'], page['rel_path'])}")
        print(f"generated {path}")

    home_pages = [
        p for p in pages if "/" not in p["rel_path"] and p["rel_path"] not in HOME_EXCLUDED
    ]
    index_path = os.path.join(docs_dir, "index.md")
    with open(index_path, "w") as fh:
        fh.write(build_index(home_pages))
    print(f"generated {index_path}")

    config_path = os.path.join(wiki_dir, "mkdocs.yml")
    with open(config_path) as fh:
        config = yaml.safe_load(fh)
    config["nav"] = build_nav(pages)
    with open(config_path, "w") as fh:
        yaml.safe_dump(config, fh, sort_keys=False, allow_unicode=True)
    print(f"generated {config_path}")


if __name__ == "__main__":
    main()
