#!/usr/bin/env python3
"""
Script ponctuel : attache les captures d'achat locales aux fiches Matériel correspondantes
(champ Photo), preuve d'achat pour Decathlon (sac/sifflet) et Vinted (ballons d'occasion).

Usage :
    python scripts/seed_materiel_photos_2026.py          # dry-run
    python scripts/seed_materiel_photos_2026.py --write   # uploade réellement
"""

import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
VCM_ROOT = ROOT.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env_file(ROOT / ".env")
TOKEN = os.environ.get("AIRTABLE_TOKEN")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
WRITE = "--write" in sys.argv

PHOTO_FIELD_ID = "fld3ZsCSYKA9v4XoZ"  # Matériel.Photo

ATTACHMENTS = [
    ("recfSBSQah9TSt583", "Sifflet poire", VCM_ROOT / "achats decathlon.jpg"),
    ("recjJrAxrKNVgS9wZ", "Sac à ballons", VCM_ROOT / "achats decathlon.jpg"),
    ("recZcQuH1yTRXGP6V", "8 ballons de volley d'occasion", VCM_ROOT / "achats vinted.jpg"),
    ("recZcQuH1yTRXGP6V", "8 ballons de volley d'occasion", VCM_ROOT / "molten-5000-x1.jpg"),
    ("recZcQuH1yTRXGP6V", "8 ballons de volley d'occasion", VCM_ROOT / "molten-5000-x3.png"),
    ("recZcQuH1yTRXGP6V", "8 ballons de volley d'occasion", VCM_ROOT / "V5M4000-VB-680x680.png"),
]


def upload_attachment(record_id: str, file_path: Path):
    content_type = mimetypes.guess_type(file_path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
    url = f"https://content.airtable.com/v0/{BASE_ID}/{record_id}/{PHOTO_FIELD_ID}/uploadAttachment"
    body = json.dumps({"contentType": content_type, "file": b64, "filename": file_path.name}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        time.sleep(0.25)
        return json.loads(resp.read().decode("utf-8"))


def main():
    print(f"Mode : {'ÉCRITURE' if WRITE else 'dry-run'}\n")
    for record_id, label, fp in ATTACHMENTS:
        print(f"  - {label} <- {fp.name} ({'trouvé' if fp.exists() else 'INTROUVABLE'})")

    if not WRITE:
        print("\nDry-run terminé. Relance avec --write pour uploader réellement.")
        return

    for record_id, label, fp in ATTACHMENTS:
        if not fp.exists():
            print(f"  ! Fichier introuvable, ignoré : {fp.name}")
            continue
        upload_attachment(record_id, fp)
        print(f"  + {fp.name} attaché à {label}")

    print("\nTerminé.")


if __name__ == "__main__":
    main()
