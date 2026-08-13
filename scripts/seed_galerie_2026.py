#!/usr/bin/env python3
"""
Script ponctuel : crée des enregistrements Galerie et y attache directement les photos
locales du dossier 010_PHOTOS (upload via l'API de contenu Airtable, pas besoin d'URL
publique).

Usage :
    python scripts/seed_galerie_2026.py          # dry-run (liste sans écrire ni uploader)
    python scripts/seed_galerie_2026.py --write   # crée les enregistrements et uploade les photos
"""

import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PHOTOS_DIR = ROOT.parent / "010_PHOTOS"


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


def airtable_request(table: str, method: str, body: dict | None = None) -> dict:
    table_name, _, query = table.partition("?")
    url = f"https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table_name)}"
    if query:
        url += f"?{query}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        time.sleep(0.25)
        return json.loads(resp.read().decode("utf-8"))


def upload_attachment(record_id: str, field_id: str, file_path: Path):
    content_type = mimetypes.guess_type(file_path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
    url = f"https://content.airtable.com/v0/{BASE_ID}/{record_id}/{field_id}/uploadAttachment"
    body = json.dumps({"contentType": content_type, "file": b64, "filename": file_path.name}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        time.sleep(0.25)
        return json.loads(resp.read().decode("utf-8"))


PHOTOS = [
    {
        "file": "WhatsApp Image 2026-05-26 at 20.36.25.jpeg",
        "titre": "Entraînement d'été en extérieur (1)",
        "date": "2026-05-26",
        "publication_titre": "Entraînement d'été (moustiques)",
    },
    {
        "file": "WhatsApp Image 2026-05-26 at 20.51.02.jpeg",
        "titre": "Entraînement d'été en extérieur (2)",
        "date": "2026-05-26",
        "publication_titre": "Entraînement d'été (moustiques)",
    },
    {
        "file": "WhatsApp Image 2026-04-12 at 16.32.26.jpeg",
        "titre": "Entraînement — avril 2026",
        "date": "2026-04-12",
        "publication_titre": None,
    },
    {
        "file": "1763545131896.jpg",
        "titre": "Photo d'équipe au gymnase (1)",
        "date": "2025-11-19",
        "publication_titre": None,
    },
    {
        "file": "1763545131903.jpg",
        "titre": "Photo d'équipe au gymnase (2)",
        "date": "2025-11-19",
        "publication_titre": None,
    },
]


def main():
    print(f"Mode : {'ÉCRITURE + UPLOAD' if WRITE else 'dry-run'}\n")
    for p in PHOTOS:
        fp = PHOTOS_DIR / p["file"]
        exists = fp.exists()
        print(f"  - {p['titre']} <- {p['file']} ({'trouvé' if exists else 'INTROUVABLE'})")

    if not WRITE:
        print("\nDry-run terminé. Relance avec --write pour créer les enregistrements et uploader les photos.")
        return

    if not TOKEN or not BASE_ID:
        print("Il manque AIRTABLE_TOKEN / AIRTABLE_BASE_ID.")
        sys.exit(1)

    print("\nCréation des enregistrements et upload des photos...")
    for p in PHOTOS:
        fp = PHOTOS_DIR / p["file"]
        if not fp.exists():
            print(f"  ! Fichier introuvable, ignoré : {p['file']}")
            continue

        fields = {"Titre": p["titre"], "Date": p["date"], "Type": "Photo"}
        if p["publication_titre"]:
            pub = airtable_request(
                "Publications?" + urllib.parse.urlencode({"filterByFormula": f'{{Titre}}="{p["publication_titre"]}"'}),
                "GET",
            )
            if pub["records"]:
                fields["Publications"] = [pub["records"][0]["id"]]

        rec = airtable_request("Galerie", "POST", {"records": [{"fields": fields}]})
        record_id = rec["records"][0]["id"]
        print(f"  + Enregistrement créé pour {p['titre']} ({record_id})")

        upload_attachment(record_id, FICHIERS_FIELD_ID, fp)
        print(f"    -> photo uploadée ({fp.stat().st_size // 1024} Ko)")

    print("\nTerminé.")


FICHIERS_FIELD_ID = "fld79jGGfe5wGOCO0"  # Galerie.Fichiers, résolu via l'API meta au préalable

if __name__ == "__main__":
    main()
