#!/usr/bin/env python3
"""
Script ponctuel (one-off) : peuple la base avec des données réelles du club.
- Lieux : Gymnase du collège de Mauvezin, Stade Marcel Gilard.
- Événements : un "Anniversaire" par membre (prochaine occurrence à partir d'aujourd'hui),
  + le tournoi "Volley sur Gazon" du 4 octobre 2026.
- Créneaux : entraînements récurrents (mardi 20h-22h, samedi 10h-12h) à partir du
  1er septembre 2026 — dans Créneaux, pas Événements, pour ne pas créer une ligne
  Événement/Présence par semaine indéfiniment.

Usage :
    python scripts/seed_evenements_2026.py          # dry-run
    python scripts/seed_evenements_2026.py --write   # écrit réellement dans Airtable
"""

import datetime
import json
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
TODAY = datetime.date.today()


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


def next_occurrence(birth_date: datetime.date, today: datetime.date) -> datetime.date:
    try:
        this_year = birth_date.replace(year=today.year)
    except ValueError:  # 29 février
        this_year = birth_date.replace(year=today.year, day=28)
    return this_year if this_year >= today else this_year.replace(year=today.year + 1)


def get_all_membres() -> list[dict]:
    records, offset = [], None
    while True:
        qs = "?pageSize=100" + (f"&offset={offset}" if offset else "")
        data = airtable_request(f"Membres{qs}", "GET")
        records.extend(data["records"])
        offset = data.get("offset")
        if not offset:
            break
    return records


def create_records(table: str, records: list[dict]) -> list[dict]:
    created = []
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        if WRITE:
            resp = airtable_request(table, "POST", {"records": batch})
            created.extend(resp["records"])
        else:
            created.extend(batch)
    return created


def main():
    print(f"Date du jour : {TODAY.isoformat()} — mode : {'ÉCRITURE' if WRITE else 'dry-run'}\n")

    # 1) Lieux
    lieux_specs = [
        {"fields": {"Nom du lieu": "Gymnase du collège de Mauvezin", "Ville": "Mauvezin"}},
        {"fields": {"Nom du lieu": "Stade Marcel Gilard", "Ville": "Mauvezin"}},
    ]
    print("Lieux à créer :")
    for l in lieux_specs:
        print(f"  - {l['fields']['Nom du lieu']}")
    lieux = create_records("Lieux", lieux_specs)
    gymnase_id = lieux[0]["id"] if WRITE else None
    stade_id = lieux[1]["id"] if WRITE else None

    # 2) Anniversaires — un par membre, prochaine occurrence
    if not TOKEN or not BASE_ID:
        print("\nIl manque AIRTABLE_TOKEN / AIRTABLE_BASE_ID pour lire les membres réels.")
        membres = []
    else:
        membres = get_all_membres()

    anniv_specs = []
    print(f"\n{len(membres)} membres lus — anniversaires à créer :")
    for m in membres:
        f = m["fields"]
        naissance = f.get("Date de naissance")
        if not naissance:
            continue
        bdate = datetime.date.fromisoformat(naissance)
        occ = next_occurrence(bdate, TODAY)
        nom_complet = f"{f.get('Prénom', '')} {f.get('Nom', '')}".strip()
        print(f"  - Anniversaire de {nom_complet} -> {occ.isoformat()}")
        anniv_specs.append(
            {
                "fields": {
                    "Nom événement": f"Anniversaire de {nom_complet}",
                    "Type": "Anniversaire",
                    "Interne/Externe": "Interne",
                    "Date": occ.isoformat(),
                    "Statut": "Publié",
                    "Responsable(s)": [m["id"]],
                }
            }
        )

    # 3) Tournoi Volley sur Gazon
    tournoi_spec = {
        "fields": {
            "Nom événement": "Tournoi Volley sur Gazon — 1ère édition",
            "Type": "Tournoi",
            "Interne/Externe": "Interne",
            "Date": "2026-10-04",
            "Heure début": "09:00",
            "Description": (
                "Stade Marcel Gilard, Mauvezin. Organisé et animé par le Volley Club "
                "Mauvezin (Les Canards Flambés). 4 joueurs minimum par équipe, tous "
                "niveaux, 15€ par équipe. Buvette & petite restauration."
            ),
            "Statut": "Publié",
        }
    }
    if WRITE:
        tournoi_spec["fields"]["Lieu"] = [stade_id]
    print(f"\nTournoi à créer : {tournoi_spec['fields']['Nom événement']} (04/10/2026, Stade Marcel Gilard)")

    evenements_specs = anniv_specs + [tournoi_spec]
    create_records("Événements", evenements_specs)

    # 4) Créneaux d'entraînement récurrents
    creneaux_specs = [
        {
            "fields": {
                "Référence": "Entraînement du mardi soir",
                "Jour": "Mardi",
                "Heure début": "20:00",
                "Heure fin": "22:00",
                "Statut": "Actif",
                "Notes": "À partir du 1er septembre 2026 (nouvelle saison).",
            }
        },
        {
            "fields": {
                "Référence": "Entraînement du samedi matin",
                "Jour": "Samedi",
                "Heure début": "10:00",
                "Heure fin": "12:00",
                "Statut": "Actif",
                "Notes": "À partir du 1er septembre 2026 (nouvelle saison).",
            }
        },
    ]
    if WRITE:
        for c in creneaux_specs:
            c["fields"]["Lieu"] = [gymnase_id]
    print("\nCréneaux à créer :")
    for c in creneaux_specs:
        print(f"  - {c['fields']['Référence']} ({c['fields']['Jour']} {c['fields']['Heure début']}-{c['fields']['Heure fin']})")
    create_records("Créneaux", creneaux_specs)

    if not WRITE:
        print("\nDry-run terminé (rien n'a été écrit). Relance avec --write pour créer réellement ces enregistrements.")
    else:
        print(f"\nTerminé : {len(lieux)} lieux, {len(evenements_specs)} événements, {len(creneaux_specs)} créneaux créés.")


if __name__ == "__main__":
    main()
