"""Build a source-only archive using an explicit file allowlist."""

import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    ".env.example",
    "android/settings.gradle.kts",
    "android/build.gradle.kts",
    "android/gradle.properties",
    "android/gradlew",
    "android/gradlew.bat",
    "android/gradle/wrapper/gradle-wrapper.jar",
    "android/gradle/wrapper/gradle-wrapper.properties",
    "android/app/build.gradle.kts",
    "releases/README.md",
    "releases/SHA256.txt",
}
TREES = (
    "backend/callshield/",
    "backend/tests/",
    "android/app/src/",
    "scripts/",
    "docs/",
)
TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".java",
    ".xml",
    ".yml",
    ".toml",
    ".kts",
    ".json",
    ".properties",
    ".example",
    ".txt",
}


def release_files():
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or not path.is_file():
            continue
        if any(
            part
            in {"__pycache__", ".venv", ".git", ".gradle", "build", "runtime", "dist"}
            for part in path.relative_to(ROOT).parts
        ):
            continue
        if relative not in FILES and not relative.startswith(TREES):
            continue
        if path.suffix in {".pyc", ".db", ".wav", ".aiff", ".apk", ".jks", ".keystore"}:
            raise ValueError(f"Runtime or private file in source allowlist: {relative}")
        if re.search(r"[\u3400-\u9fff]", relative):
            raise ValueError(f"Non-English filename: {relative}")
        if path.suffix in TEXT_SUFFIXES or path.name in {"LICENSE", ".gitignore"}:
            content = path.read_text(encoding="utf-8")
            if ("/" + "Users" + "/") in content or re.search(
                r"(?:sk-proj-|tvly-|ghp_|gho_)[A-Za-z0-9_-]{24,}", content
            ):
                raise ValueError(f"Possible local path or credential: {relative}")
            if re.search(r"[\u3400-\u9fff]", content):
                raise ValueError(f"Untranslated text: {relative}")
        yield path, relative


if __name__ == "__main__":
    output = ROOT / "dist" / "CallShield-Agent-v0.2.0-source.zip"
    output.parent.mkdir(exist_ok=True)
    files = list(release_files())
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, relative in files:
            archive.write(path, "callshield-agent/" + relative)
    (output.parent / "SOURCE-SHA256.txt").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )
    print(f"Packaged {len(files)} source files: {output.name}")
