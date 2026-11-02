"""Воспроизводимая проверка без сторонних библиотек: python tools/verify.py."""

from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence"


def main():
    OUT.mkdir(exist_ok=True)
    checks = [
        ("tests", ["-m", "unittest", "discover", "-s", "tests", "-v"], 0),
        ("demo", ["lab1.py", "--demo"], 0),
        ("demo_file", ["lab1.py", "--file", "examples/demo.txt"], 0),
        ("negative", ["lab1.py", "--file", "examples/negative.txt"], 1),
        ("compile", ["-m", "compileall", "-q", "lab1.py", "proofchecker", "tests", "tools"], 0),
    ]
    results = []
    version = f"python{sys.version_info.major}{sys.version_info.minor}"
    for name, args, expected in checks:
        run = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                             encoding="utf-8", errors="replace")
        log = OUT / f"{name}_{version}.txt"
        log.write_text(f"Python: {platform.python_version()}\nCommand: python {' '.join(args)}\n"
                       f"Exit: {run.returncode}; expected: {expected}\n\n"
                       + run.stdout + run.stderr, encoding="utf-8")
        results.append({"name": name, "args": args, "exit": run.returncode,
                        "expected_exit": expected, "passed": run.returncode == expected,
                        "log": str(log.relative_to(ROOT))})
    manifest = json.loads((ROOT / "docs/MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
    originals = []
    for entry in manifest:
        path = ROOT / Path(entry["file"].replace("\\", "/"))
        # В отдельном переносимом комплекте оригиналов может не быть.
        state = "not_in_package"
        if path.exists():
            state = "unchanged" if hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"] else "CHANGED"
        originals.append({"file": entry["file"], "state": state})
    passed = all(x["passed"] for x in results) and all(x["state"] != "CHANGED" for x in originals)
    summary = {"python": platform.python_version(), "platform": platform.platform(),
               "interpreter": sys.executable, "checks": results, "originals": originals,
               "passed": passed}
    (OUT / f"verification_{version}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"python": summary["python"], "checks": len(results),
                      "passed": passed, "originals_unchanged": sum(x["state"] == "unchanged" for x in originals)},
                     ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
