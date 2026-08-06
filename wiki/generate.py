#!/usr/bin/env python3
"""Generate the Crisis Cadres wiki markdown pages.

The wiki's content lives as committed markdown pages under docs/. A directory
with an index.md becomes a sidebar section (its "main topic"); the other pages
in the directory become sub-topics nested under it. Sections may nest: a
sub-directory with an index.md is rendered as a child section of its parent.
Any .md file is normalized with the discussion footer, and the mkdocs
navigation and homepage are regenerated from the directory structure.

This script:
  1. normalizes every page — strips any stale footer and re-appends the
     discussion footer,
  2. regenerates the homepage (index.md) from the top-level sections and
     standalone pages,
  3. regenerates the nav in mkdocs.yml from the docs tree.
"""

import os
import re
import urllib.parse

import yaml

REPO = "crisis-cadres/praxis-hub"
ISSUES_URL = f"https://github.com/{REPO}/issues"
FOOTER_START = "\n---\n\n**[Start a discussion]("

# Top-level pages that get their own wiki page but are excluded from the
# assembled homepage (e.g. "The Authors").
HOME_EXCLUDED = {"salish-sea-cadre"}

# Pages to keep in docs/ (with footers) but hide from the sidebar nav.
# Remove a slug from this set to reveal the page again.
NAV_EXCLUDED = set()

# Ordered list of directory names. Sections follow this order in the homepage
# and nav; directories not listed fall back to alphabetical order.
SECTION_ORDER = [
    "philosophy",
    "cadres",
    "pillars",
    "strategy",
    "governance",
    "praxis-hub",
    "appendices",
]


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


def read_page(docs_dir, rel_path):
    with open(os.path.join(docs_dir, rel_path + ".md")) as fh:
        content = fh.read()
    clean = strip_footer(content)
    lines = clean.splitlines()
    title = lines[0].lstrip("#").strip()
    body = "\n".join(lines[1:]).strip()
    return {"rel_path": rel_path, "title": title, "body": body}


def ordered_names(names):
    ranked = {name: i for i, name in enumerate(SECTION_ORDER)}
    return sorted(names, key=lambda n: (ranked.get(n, len(SECTION_ORDER)), n))


def build_section(docs_dir, rel_dir):
    dir_path = os.path.join(docs_dir, rel_dir)
    index_rel = os.path.join(rel_dir, "index")
    if not os.path.exists(os.path.join(docs_dir, index_rel + ".md")):
        return None

    index = read_page(docs_dir, index_rel)

    children = []
    for subdir in ordered_names(
        d for d in os.listdir(dir_path)
        if os.path.isdir(os.path.join(dir_path, d))
    ):
        sub = build_section(docs_dir, os.path.join(rel_dir, subdir))
        if sub:
            children.append(("section", sub))

    for filename in sorted(
        f for f in os.listdir(dir_path)
        if f.endswith(".md") and f != "index.md"
    ):
        rel = os.path.join(rel_dir, filename[: -len(".md")])
        if rel in NAV_EXCLUDED:
            continue
        children.append(("page", read_page(docs_dir, rel)))

    return {"rel_dir": rel_dir, "index": index, "children": children}


def collect(docs_dir):
    top = []
    for entry in ordered_names(os.listdir(docs_dir)):
        full = os.path.join(docs_dir, entry)
        if os.path.isdir(full):
            section = build_section(docs_dir, entry)
            if section:
                top.append(("section", section))

    standalone = []
    for filename in sorted(
        f for f in os.listdir(docs_dir)
        if f.endswith(".md") and f != "index.md"
    ):
        rel = filename[: -len(".md")]
        if rel in NAV_EXCLUDED:
            continue
        standalone.append(("page", read_page(docs_dir, rel)))
    return top, standalone


def write_page(docs_dir, page):
    rel_path = page["rel_path"]
    path = os.path.join(docs_dir, rel_path + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(f"# {page['title']}\n\n{page['body']}{footer(page['title'], rel_path)}")
    print(f"generated {path}")


def collect_all_pages(top, standalone):
    pages = []

    def walk(items):
        for kind, node in items:
            if kind == "section":
                pages.append(node["index"])
                walk(node["children"])
            else:
                pages.append(node)

    walk(top)
    walk(standalone)
    return pages


LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def homepage_links(body, rel_dir):
    """Rewrite relative links in a section index body so they resolve from the
    homepage (docs root). Section bodies are embedded into the homepage one
    directory deeper than where they live, so same-section targets gain a
    ``rel_dir/`` prefix and parent-relative targets lose one ``../``.
    """

    def repl(match):
        target = match.group(2).strip()
        if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
            return match.group(0)
        if target.startswith("../"):
            target = target[len("../"):]
        else:
            target = f"{rel_dir}/{target}"
        return f"[{match.group(1)}]({target})"

    return LINK_RE.sub(repl, body)


def build_index(top, standalone):
    lines = ["# Crisis Cadres\n"]
    for kind, node in top:
        if kind == "section":
            idx = node["index"]
            lines.append(f"## [{idx['title']}]({idx['rel_path']}.md)\n")
            lines.append(homepage_links(idx["body"], node["rel_dir"]))
        else:
            if node["rel_path"] in HOME_EXCLUDED:
                continue
            lines.append(f"## [{node['title']}]({node['rel_path']}.md)\n")
            lines.append(node["body"])
        lines.append("")
    return "\n".join(lines).rstrip() + footer("Crisis Cadres", "index")


def nav_items(node):
    if node["children"]:
        items = [node["index"]["rel_path"] + ".md"]
        for kind, child in node["children"]:
            if kind == "section":
                items.append({child["index"]["title"]: nav_items(child)})
            else:
                items.append({child["title"]: child["rel_path"] + ".md"})
        return items
    return node["index"]["rel_path"] + ".md"


def build_nav(top, standalone):
    nav = [{"Home": "index.md"}]
    for kind, node in top:
        if kind == "section":
            nav.append({node["index"]["title"]: nav_items(node)})
        else:
            nav.append({node["title"]: node["rel_path"] + ".md"})
    for _, node in standalone:
        nav.append({node["title"]: node["rel_path"] + ".md"})
    return nav


def main():
    wiki_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(wiki_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    top, standalone = collect(docs_dir)

    for page in collect_all_pages(top, standalone):
        write_page(docs_dir, page)

    index_path = os.path.join(docs_dir, "index.md")
    with open(index_path, "w") as fh:
        fh.write(build_index(top, standalone))
    print(f"generated {index_path}")

    config_path = os.path.join(wiki_dir, "mkdocs.yml")
    with open(config_path) as fh:
        config = yaml.safe_load(fh)
    config["nav"] = build_nav(top, standalone)
    with open(config_path, "w") as fh:
        yaml.safe_dump(config, fh, sort_keys=False, allow_unicode=True)
    print(f"generated {config_path}")


if __name__ == "__main__":
    main()
