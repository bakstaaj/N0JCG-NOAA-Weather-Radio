from pathlib import Path
import hashlib
import tarfile

root = Path(__file__).resolve().parents[1]
version = (root / "VERSION").read_text().strip()
out = root / "release" / f"N0JCG-NOAA-WEATHER-RADIO-v{version}.tar.gz"
out.parent.mkdir(exist_ok=True)
with tarfile.open(out, "w:gz") as archive:
    for path in root.iterdir():
        if path.name not in {".git", ".venv", "release", "runtime", "__pycache__"}:
            archive.add(path, arcname=f"N0JCG-NOAA-WEATHER-RADIO-v{version}/{path.name}")
digest = hashlib.sha256(out.read_bytes()).hexdigest()
(out.with_suffix(out.suffix + ".sha256")).write_text(f"{digest}  {out.name}\n")
print(out)
