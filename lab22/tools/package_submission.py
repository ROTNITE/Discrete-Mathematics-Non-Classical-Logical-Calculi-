"""Собрать комплект, сверить SHA-256 каждой записи и проверить извлеченную копию."""

from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "LR1_variant3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    (ROOT / "output").mkdir(exist_ok=True)
    paths = [ROOT / name for name in ("README.md", "lab1.py", "start.cmd", ".gitignore")]
    for folder in ("proofchecker", "tests", "examples", "docs", "tools", "evidence"):
        paths.extend(p for p in (ROOT / folder).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"))
    paths.extend(ROOT / "output" / name for name in ("LR1_variant3.docx", "LR1_variant3.pdf"))
    entries = []
    archive = ROOT / "output/LR1_variant3.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for path in sorted(paths):
            path.resolve().relative_to(ROOT.resolve())
            data = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            z.writestr(f"{ARCHIVE_ROOT}/{name}", data)
            entries.append({"path": name, "bytes": len(data), "sha256": sha(data)})
        z.writestr(f"{ARCHIVE_ROOT}/PACKAGE_MANIFEST.json",
                   json.dumps(entries, ensure_ascii=False, indent=2).encode("utf-8"))
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("Ошибка CRC архива")
        for entry in entries:
            data = z.read(f"{ARCHIVE_ROOT}/{entry['path']}")
            if sha(data) != entry["sha256"]:
                raise RuntimeError(f"Не совпал SHA-256: {entry['path']}")
        temp_root = ROOT / "tmp"
        temp_root.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="package_check_", dir=temp_root)
        extract = Path(temporary.name).resolve()
        # Проверка границы до извлечения и рекурсивной очистки.
        extract.relative_to(temp_root.resolve())
        try:
            for item in z.infolist():
                (extract / item.filename).resolve().relative_to(extract)
            z.extractall(extract)
            extracted_root = extract / ARCHIVE_ROOT
            for entry in entries:
                if sha((extracted_root / entry["path"]).read_bytes()) != entry["sha256"]:
                    raise RuntimeError(f"Не совпал извлеченный файл: {entry['path']}")
            results = []
            for args, expected in ((["lab1.py", "--demo"], 0),
                                   (["lab1.py", "--file", "examples/negative.txt"], 1),
                                   (["-m", "unittest", "discover", "-s", "tests", "-q"], 0)):
                run = subprocess.run([sys.executable, *args], cwd=extracted_root,
                                     capture_output=True, encoding="utf-8", errors="replace")
                results.append({"args": args, "exit": run.returncode, "expected": expected,
                                "stdout": run.stdout, "stderr": run.stderr})
                if run.returncode != expected:
                    raise RuntimeError(f"Не прошла проверка извлеченного комплекта: {args}\n{run.stderr}")
        finally:
            extract.relative_to(temp_root.resolve())
            temporary.cleanup()
    verification = {"archive": archive.name, "bytes": archive.stat().st_size,
                    "sha256": sha(archive.read_bytes()), "crc": "OK",
                    "payload_files": len(entries), "zip_entries": len(entries) + 1,
                    "all_entry_hashes_verified": True, "all_extracted_hashes_verified": True,
                    "python": platform.python_version(), "extracted_checks": results,
                    "physical_other_pc_tested": False}
    (ROOT / "output/packaging_verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in verification.items() if k != "extracted_checks"}, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
