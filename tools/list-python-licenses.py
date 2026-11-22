"""Prints a Markdown table of all installed Python distributions and their declared licenses.

Usage (from the repository root):
  docker run --rm -i --entrypoint python librevdi-broker:local - < tools/list-python-licenses.py \
    > docs/licenses/broker-python-packages.md
"""

import importlib.metadata as md

rows: dict[str, tuple[str, str, str]] = {}
for dist in md.distributions():
    meta = dist.metadata
    name = meta["Name"]
    if not name or name.lower() in rows:
        continue
    lic = meta.get("License-Expression") or ""
    if not lic:
        classifiers = [
            c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")
        ]
        lic = "; ".join(classifiers)
    if not lic:
        raw = (meta.get("License") or "").strip().splitlines()
        lic = raw[0][:60] if raw else "UNKNOWN"
    rows[name.lower()] = (name, dist.version, lic.replace("|", "/"))

print("# Python packages in the broker image\n")
print("Generated from the package metadata inside the image with `tools/list-python-licenses.py`.")
print("The license column is what each package declares; it has not been verified by hand.\n")
print("| Package | Version | License (declared) |")
print("|---|---|---|")
for key in sorted(rows):
    n, v, lic = rows[key]
    print(f"| {n} | {v} | {lic} |")
