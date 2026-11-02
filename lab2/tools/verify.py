"""Воспроизводимые проверки приложения, UTF-8 и сохранности исходных материалов."""

from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    out = ROOT / "evidence"
    out.mkdir(exist_ok=True)
    version = f"python{sys.version_info.major}{sys.version_info.minor}"
    checks = [
        ("tests", ["-m", "unittest", "discover", "-s", "tests", "-v"], 0, None),
        ("compile", ["-m", "compileall", "-q", "lab2.py", "multilogic", "tests", "tools"], 0, None),
        ("variant", ["lab2.py", "variant"], 0, None),
        ("eval_k3", ["lab2.py", "eval", "p->q", "--logic", "k3", "--values", "p=1/2,q=1/2"], 0, None),
        ("eval_l3", ["lab2.py", "eval", "p->q", "--logic", "l3", "--values", "p=1/2,q=1/2"], 0, None),
        ("compare", ["lab2.py", "compare", "(p->q)->(~q->~p)"], 0, None),
        ("entails_half", ["lab2.py", "entails", "--premise", "p->q", "--premise", "q->p",
                          "--conclusion", "p|~p", "--logic", "l3"], 0, None),
        ("vacuous", ["lab2.py", "entails", "--premise", "p", "--premise", "~p", "--conclusion", "q"], 0, None),
        ("negative_syntax", ["lab2.py", "analyze", "p->"], 2, None),
        ("negative_value", ["lab2.py", "eval", "p", "--logic", "classic", "--values", "p=1/2"], 2, None),
        ("interactive", ["lab2.py"], 0, (ROOT / "examples/session.txt").read_text(encoding="utf-8")),
    ]
    results = []
    for name, args, expected, input_text in checks:
        started = time.perf_counter()
        run = subprocess.run([sys.executable, "-X", "utf8", *args], cwd=ROOT, input=input_text,
                             capture_output=True, encoding="utf-8", timeout=90)
        elapsed = time.perf_counter() - started
        log = out / f"{name}_{version}.txt"
        log.write_text(f"Python: {platform.python_version()}\nCommand arguments: {json.dumps(args, ensure_ascii=False)}\n"
                       f"Exit: {run.returncode}; expected: {expected}\nSeconds: {elapsed:.6f}\n\n"
                       + run.stdout + run.stderr, encoding="utf-8")
        results.append({"name": name, "args": args, "exit": run.returncode, "expected_exit": expected,
                        "passed": run.returncode == expected, "seconds": elapsed,
                        "log": log.relative_to(ROOT).as_posix()})
    manifest = json.loads((ROOT / "docs/MATERIALS_MANIFEST.json").read_text(encoding="utf-8"))
    materials = []
    for entry in manifest:
        relative = Path(entry["file"])
        path = ROOT.joinpath(*relative.parts[1:]) if relative.parts[0] == "lab2" else ROOT.parent / relative
        state = "not_in_package"
        if path.is_file():
            state = "unchanged" if hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"] else "CHANGED"
        materials.append({"file": entry["file"], "state": state})
    source_files = [ROOT / "lab2.py", ROOT / "start.cmd"]
    for directory in ("multilogic", "tests"):
        source_files.extend((ROOT / directory).glob("*.py"))
    hashes = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(source_files)}
    passed = all(result["passed"] for result in results) and all(item["state"] != "CHANGED" for item in materials)
    summary = {"python": platform.python_version(), "platform": platform.platform(), "interpreter": sys.executable,
               "checks": results, "materials": materials, "source_sha256": hashes, "passed": passed}
    (out / f"verification_{version}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"python": summary["python"], "checks": len(results), "passed": passed,
                      "materials_unchanged": sum(item["state"] == "unchanged" for item in materials)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
