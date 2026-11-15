import json
import re
import subprocess
from pathlib import Path

ROOT = Path(".")
README_PATH = ROOT / "README.md"
TITLE = "### 📝 Complete TODO List"
SKIP_DIRS = {".git", ".github", ".venv", "venv", "node_modules"}

ENTRY_RE = re.compile(
    r'^- \[ \] \*\*(?P<path>.+?):(?P<line>\d+)\*\* - (?P<message>.*)$'
)
TODO_RE = re.compile(
    r'#\s*TODO\b\s*(?:\((?P<author>[^)]*)\))?\s*:?\s*(?P<message>.*?)\s*$'
)


def run_git(args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def is_python_file(path):
    return path.is_file() and path.suffix == ".py" and not any(part in SKIP_DIRS for part in path.parts)


def collect_python_files():
    return sorted(path for path in ROOT.rglob("*.py") if is_python_file(path))


def parse_todos(path):
    todos = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = TODO_RE.search(line)
        if not match:
            continue
        author = (match.group("author") or "").strip()
        message = (match.group("message") or "").strip()
        if author:
            message = f"({author}) {message}".strip()
        todos.append({"path": path.as_posix(), "line": line_number, "message": message})
    return todos


def collect_all_todos():
    by_path = {}
    for path in collect_python_files():
        todos = parse_todos(path)
        if todos:
            by_path[path.as_posix()] = todos
    return by_path


def parse_readme():
    text = README_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        title_index = next(i for i, line in enumerate(lines) if line.strip() == TITLE)
    except StopIteration as exc:
        raise RuntimeError("Complete TODO List title not found") from exc
    end_index = next((i for i in range(title_index + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    entries = []
    for raw in lines[title_index + 1:end_index]:
        match = ENTRY_RE.match(raw)
        if not match:
            continue
        item = match.groupdict()
        item["line"] = int(item["line"])
        entries.append(item)
    return text, lines, title_index, end_index, entries


def changed_python_files():
    run_git(["fetch", "origin", "main"])
    output = run_git(["diff", "--name-only", "origin/main", "HEAD"])
    paths = []
    for name in output.splitlines():
        path = Path(name)
        if path.suffix == ".py" and is_python_file(path):
            paths.append(name)
    return sorted(paths)


def sort_key(item):
    return (item["path"], item["line"], item["message"])


def render_entry(item):
    return f"- [ ] **{item['path']}:{item['line']}** - {item['message']}"


def main():
    current_by_path = collect_all_todos()
    current_all = [item for items in current_by_path.values() for item in items]
    old_text, lines, title_index, end_index, baseline = parse_readme()
    changed_paths = changed_python_files()

    print("Changed Python files:")
    for path in changed_paths:
        print(f"  {path}")
    print("\nCurrent TODO count by file:")
    for path in sorted(current_by_path):
        print(f"  {path}: {len(current_by_path[path])}")
    print(f"Current TODO total in scanned .py files: {len(current_all)}")
    print(f"Baseline README TODO entries: {len(baseline)}")

    next_entries = []
    for item in baseline:
        if item["path"] not in changed_paths:
            next_entries.append({"path": item["path"], "line": item["line"], "message": item["message"]})
    for path in changed_paths:
        next_entries.extend(current_by_path.get(path, []))
    next_entries = sorted(next_entries, key=sort_key)

    keys = [sort_key(item) for item in next_entries]
    if keys != sorted(keys):
        raise RuntimeError("Generated README TODO entries are not sorted by path and line.")
    if old_text.count(TITLE) != 1:
        raise RuntimeError("The README TODO section title must remain unchanged and unique.")

    rendered = [render_entry(item) for item in next_entries]
    new_lines = lines[:title_index + 1] + [""] + rendered + [""] + lines[end_index:]
    new_text = "\n".join(new_lines)
    if old_text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    README_PATH.write_text(new_text, encoding="utf-8")

    baseline_by_path = {}
    for item in baseline:
        baseline_by_path.setdefault(item["path"], []).append(item)

    print("\nApplied changes for main-to-dev Python files:")
    for path in changed_paths:
        old_items = baseline_by_path.get(path, [])
        new_items = current_by_path.get(path, [])
        old_set = {(i["line"], i["message"]) for i in old_items}
        new_set = {(i["line"], i["message"]) for i in new_items}
        print(f"\n{path}")
        print("  Removed or replaced entries:")
        for line, message in sorted(old_set - new_set):
            print(f"    - line {line}: {message}")
        print("  Added or updated entries:")
        for line, message in sorted(new_set - old_set):
            print(f"    + line {line}: {message}")

    print(f"\nRendered README TODO entries: {len(next_entries)}")
    subprocess.run(["git", "diff", "--stat", "--", "README.md"], check=False)


if __name__ == "__main__":
    main()
