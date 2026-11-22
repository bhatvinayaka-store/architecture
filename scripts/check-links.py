#!/usr/bin/env python3
"""Check relative Markdown links and #anchors in this repo (external links are not fetched).

Usage: python3 scripts/check-links.py [root]    (default: the repo root)
Exits 1 if a link points to a missing file or heading. templates/ is skipped: its links are
placeholders that only work once a template is copied into a project.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent).resolve()
SKIP_DIRS = {".git", "node_modules", "templates"}
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
FENCE = re.compile(r"```.*?```", re.S)


def slugs(path):
    """GitHub-style heading anchors; a repeated heading gets -1, -2, ..."""
    out, seen, in_code = set(), {}, False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("```"):
            in_code = not in_code
            continue
        m = None if in_code else re.match(r"^(#{1,6})\s+(.*)$", line)
        if not m:
            continue
        s = m.group(2).strip().lower().replace("`", "")
        s = re.sub(r"[^\w\- ]", "", s).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        out.add(s if n == 0 else f"{s}-{n}")
    return out


def main():
    cache, bad, files = {}, [], 0
    for md in sorted(ROOT.rglob("*.md")):
        if SKIP_DIRS & set(md.relative_to(ROOT).parts):
            continue
        files += 1
        text = FENCE.sub("", md.read_text(encoding="utf-8"))
        for m in LINK.finditer(text):
            target = m.group(2)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # https:, mailto: ...
                continue
            path_part, _, anchor = target.partition("#")
            dest = (md.parent / path_part).resolve() if path_part else md
            if not dest.exists():
                bad.append(f"{md.relative_to(ROOT)}: missing file -> {target}")
            elif anchor and dest.suffix == ".md":
                if dest not in cache:
                    cache[dest] = slugs(dest)
                if anchor not in cache[dest]:
                    bad.append(f"{md.relative_to(ROOT)}: missing anchor -> {target}")
    print("\n".join(bad) if bad else "no broken links or anchors")
    print(f"checked {files} files")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
