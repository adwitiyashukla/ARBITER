"""Assemble a deployable Hugging Face Space from this repository.

The Space is built from the repo rather than maintained as a second copy of the code.
Only `space/app.py`, `space/README.md` and `space/requirements.txt` are written by hand;
the package and the data are copied from their canonical locations, so the demo can never
drift away from the code and results it claims to show.

    python tools/build_space.py --out ../hf-arbiter

Then commit and push that directory to your Space repo.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (source, destination inside the Space)
COPY_FILES = [
    ("space/app.py", "app.py"),
    ("space/README.md", "README.md"),
    ("space/requirements.txt", "requirements.txt"),
    ("space/.gitignore", ".gitignore"),
    ("docs/results.json", "data/results.json"),
    ("docs/judge_audit.json", "data/judge_audit.json"),
    ("LICENSE", "LICENSE"),
]
COPY_TREES = [
    ("arbiter", "arbiter"),
    ("docs/evidence", "data/evidence"),
    ("benchmark/bugs", "data/bugs"),
]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


HF_COLORS = {"red", "yellow", "green", "blue", "indigo", "purple", "pink", "gray"}
MAX_SHORT_DESCRIPTION = 60


def fail(message: str) -> int:
    print("  [fail] " + message)
    return 1


def read_frontmatter(path: str):
    """Parse the YAML block Hugging Face reads at the top of a Space README."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def validate_frontmatter(out_dir: str):
    """Catch the metadata rules locally, rather than finding out from a rejected push."""
    problems = []
    fields = read_frontmatter(os.path.join(out_dir, "README.md"))
    if fields is None:
        return ["README.md has no YAML frontmatter, so Hugging Face will not treat it as a Space"]

    desc = fields.get("short_description", "")
    if len(desc) > MAX_SHORT_DESCRIPTION:
        problems.append("short_description is {0} characters, the limit is {1}".format(
            len(desc), MAX_SHORT_DESCRIPTION))
    for key in ("colorFrom", "colorTo"):
        if fields.get(key) and fields[key] not in HF_COLORS:
            problems.append("{0} is {1!r}, must be one of: {2}".format(
                key, fields[key], ", ".join(sorted(HF_COLORS))))
    if fields.get("sdk") != "gradio":
        problems.append("sdk is {0!r}, this Space expects gradio".format(fields.get("sdk")))
    app_file = fields.get("app_file", "app.py")
    if not os.path.exists(os.path.join(out_dir, app_file)):
        problems.append("app_file points at {0}, which is not in the build".format(app_file))
    if not fields.get("emoji"):
        problems.append("emoji is required in the frontmatter")
    return problems


def build(out_dir: str, clean: bool) -> int:
    out_dir = os.path.abspath(out_dir)
    if os.path.abspath(ROOT) == out_dir:
        return fail("refusing to build into the repository itself")
    os.makedirs(out_dir, exist_ok=True)
    print("building the Space into {0}".format(out_dir))

    for rel, dest in COPY_FILES:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            return fail("missing {0}. Run the benchmark first if this is a docs/ file.".format(rel))
        target = os.path.join(out_dir, dest)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(src, target)
        print("  [ok]   {0}".format(dest))

    for rel, dest in COPY_TREES:
        src = os.path.join(ROOT, rel)
        if not os.path.isdir(src):
            return fail("missing directory {0}".format(rel))
        target = os.path.join(out_dir, dest)
        if clean and os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(src, target, dirs_exist_ok=True, ignore=IGNORE)
        count = sum(len(files) for _, _, files in os.walk(target))
        print("  [ok]   {0}/  ({1} files)".format(dest, count))

    # the demo is only worth publishing if the data behind it is actually there
    with open(os.path.join(out_dir, "data", "results.json"), encoding="utf-8") as fh:
        results = json.load(fh)
    bugs = results.get("bugs", [])
    if not bugs:
        return fail("results.json contains no bugs")

    shots = 0
    missing_evidence = []
    for bug in bugs:
        d = os.path.join(out_dir, "data", "evidence", bug["id"], "t0")
        found = [f for f in os.listdir(d)] if os.path.isdir(d) else []
        shots += len(found)
        if not found:
            missing_evidence.append(bug["id"])
    specs = len([f for f in os.listdir(os.path.join(out_dir, "data", "bugs"))
                 if f.endswith(".yaml")])

    print("\nverification")
    problems = validate_frontmatter(out_dir)
    for p in problems:
        print("  [fail] frontmatter: {0}".format(p))
    if not problems:
        print("  [ok]   Space frontmatter passes Hugging Face's metadata rules")
    print("  [ok]   {0} reports in results.json".format(len(bugs)))
    print("  [ok]   {0} bug specs".format(specs))
    print("  {0} {1} evidence screenshots".format("[ok]  " if shots else "[fail]", shots))
    if missing_evidence:
        print("  [warn] no screenshots for: {0}".format(", ".join(missing_evidence)))
    if specs != len(bugs):
        print("  [warn] {0} specs against {1} reported bugs".format(specs, len(bugs)))

    if problems:
        print("\nfix the frontmatter above before pushing, the Hub will reject it otherwise")
        return 1

    print("\nnext:")
    print("  cd {0}".format(out_dir))
    print("  git add -A && git commit -m \"ARBITER demo\" && git push")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the Space checkout to build into")
    ap.add_argument("--no-clean", action="store_true",
                    help="keep files already in the destination trees")
    args = ap.parse_args()
    return build(args.out, clean=not args.no_clean)


if __name__ == "__main__":
    sys.exit(main())
