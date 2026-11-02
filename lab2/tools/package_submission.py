"""Собрать комплект и проверить CRC, SHA-256 и запуск извлечённой копии."""

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "LR2_variant3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    paths = [ROOT / name for name in ("README.md", "lab2.py", "start.cmd")]
    for directory in ("multilogic", "tests", "docs", "examples", "tools", "materials", "evidence"):
        paths.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"))
    paths.extend(ROOT / "output" / name for name in ("LR2_variant3.docx", "LR2_variant3.pdf", "results.json", "RESULTS.md"))
    paths.extend((ROOT / "output/tables").glob("*.csv"))
    if len(list((ROOT / "output/tables").glob("*.csv"))) != 27:
        raise RuntimeError("Нужны все 27 полных таблиц")
    qa = json.loads((ROOT / "evidence/report_validation.json").read_text(encoding="utf-8"))
    if not qa["passed"]:
        raise RuntimeError("Не пройдена проверка отчёта")
    for name, expected in qa["deliverable_sha256"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise RuntimeError(f"Изменился проверенный артефакт: {name}")
    archive = ROOT / "output/LR2_variant3.zip"
    entries = []
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for path in sorted(paths):
            path.resolve().relative_to(ROOT.resolve())
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            z.writestr(f"{ARCHIVE_ROOT}/{name}", data)
            entries.append({"path": name, "bytes": len(data), "sha256": sha(data)})
        z.writestr(f"{ARCHIVE_ROOT}/PACKAGE_MANIFEST.json",
                   json.dumps(entries, ensure_ascii=False, indent=2).encode("utf-8"))
    checks = []
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("Ошибка CRC ZIP")
        for entry in entries:
            if sha(z.read(f"{ARCHIVE_ROOT}/{entry['path']}")) != entry["sha256"]:
                raise RuntimeError(f"Ошибка SHA-256 в ZIP: {entry['path']}")
        temp_root = (ROOT / "tmp").resolve()
        temp_root.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="package check ", dir=temp_root)
        extract = Path(temporary.name).resolve()
        # Проверить абсолютную границу до извлечения и рекурсивной очистки.
        extract.relative_to(temp_root)
        try:
            for item in z.infolist():
                (extract / item.filename).resolve().relative_to(extract)
            z.extractall(extract)
            extracted = extract / ARCHIVE_ROOT
            for entry in entries:
                if sha((extracted / entry["path"]).read_bytes()) != entry["sha256"]:
                    raise RuntimeError(f"Изменился извлечённый файл: {entry['path']}")
            commands = [
                (["-m", "unittest", "discover", "-s", "tests", "-q"], None),
                (["lab2.py", "variant", "--json"], None),
                (["lab2.py", "eval", "p->q", "--logic", "l3", "--values", "p=1/2,q=1/2", "--json"], None),
                (["lab2.py"], (extracted / "examples/session.txt").read_text(encoding="utf-8")),
            ]
            for args, input_text in commands:
                run = subprocess.run([sys.executable, "-X", "utf8", *args], cwd=extracted, input=input_text,
                                     capture_output=True, encoding="utf-8", timeout=90)
                if run.returncode != 0:
                    raise RuntimeError(f"Ошибка запуска извлечённого комплекта {args}: {run.stderr}")
                if args[0:2] == ["lab2.py", "variant"]:
                    expected = json.loads((ROOT / "output/results.json").read_text(encoding="utf-8"))
                    if json.loads(run.stdout) != expected:
                        raise RuntimeError("Извлечённая программа дала другие результаты варианта")
                if args[0:2] == ["lab2.py", "eval"] and json.loads(run.stdout)["value"] != "1":
                    raise RuntimeError("Неверная импликация L3 в извлечённой копии")
                checks.append({"args": args, "exit": run.returncode, "passed": True,
                               "stdout_sha256": sha(run.stdout.encode("utf-8")),
                               "stdout_excerpt": run.stdout[:1200], "stderr": run.stderr})
        finally:
            extract.relative_to(temp_root)
            temporary.cleanup()
    result = {"archive": archive.name, "bytes": archive.stat().st_size, "sha256": sha(archive.read_bytes()),
              "crc": "OK", "payload_files": len(entries), "zip_entries": len(entries) + 1,
              "all_entry_hashes_verified": True, "all_extracted_hashes_verified": True,
              "extracted_variant_matches": True, "python": platform.python_version(),
              "extracted_checks": checks, "physical_other_pc_tested": False, "passed": True}
    (ROOT / "output/packaging_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "extracted_checks"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
