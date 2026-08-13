#!/usr/bin/env python3
"""
Script ponctuel : importe les publications réelles de la page Facebook du club
(captures d'écran transmises par le trésorier le 13/08/2026), dans la table Publications.
Les photos elles-mêmes ne sont pas jointes (pas de fichier local disponible) — seul le
texte et les statistiques d'engagement visibles sont enregistrés.

Usage :
    python scripts/seed_publications_2026.py          # dry-run
    python scripts/seed_publications_2026.py --write   # écrit réellement
"""

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


def pub(titre, date, contenu, likes=None, comments=None, shares=None, evenement_id=None):
    fields = {
        "Titre": titre,
        "Plateforme": ["Facebook"],
        "Date/heure de publication": date,
        "Statut": "Publiée",
        "Contenu": contenu,
    }
    if likes is not None:
        fields["Likes"] = likes
    if comments is not None:
        fields["Commentaires"] = comments
    if shares is not None:
        fields["Partages"] = shares
    if evenement_id:
        fields["Événement lié"] = [evenement_id]
    return {"fields": fields}


def main():
    print(f"Mode : {'ÉCRITURE' if WRITE else 'dry-run'}\n")

    evenement_id = None
    if WRITE:
        r = airtable_request("Événements?" + urllib.parse.urlencode({"filterByFormula": '{Type}="Tournoi"'}), "GET")
        if r["records"]:
            evenement_id = r["records"][0]["id"]

    PUBLICATIONS = [
        pub("Lien d'inscription tournoi sur gazon", "2026-08-12T16:49:00.000Z",
            "Voici le lien pour s'inscrire au tournoi de volley sur gazon. https://www.helloasso.com/associations/volley-club-mauvezin/evenements/tournoi-de-volley-sur-gazon-mauvezin-2026 — À très bientôt sur les terrains !",
            likes=2, comments=0, shares=3, evenement_id=evenement_id),
        pub("Annonce tournoi sur gazon", "2026-08-07T00:00:00.000Z",
            "Le premier tournoi organisé par notre club ! Venez nombreux !",
            likes=2, comments=0, shares=7, evenement_id=evenement_id),
        pub("Entraînement d'été (moustiques)", "2026-05-26T00:00:00.000Z",
            "Entraînement modifié pour résister à la chaleur — merci aux moustiques pour leur participation active !",
            likes=7, comments=0, shares=2),
        pub("Soirée à St Clar Volley", "2026-02-27T00:00:00.000Z",
            "Encore une belle soirée à St Clar Volley ! Merci pour cet entraînement avec beaucoup de bonne humeur ! Au plaisir de vous retrouver à Mauvezin !",
            likes=6, comments=1),
        pub("Entraînement à Lombez", "2026-02-25T00:00:00.000Z",
            "Hier soir nous avons été tester nos techniques à Lombez et nous avons appris beaucoup de choses essentielles pour évoluer encore ! Merci VOLLEY LOMBEZ ! Au plaisir de se retrouver à Mauvezin !",
            likes=4, comments=1, shares=1),
        pub("Vœux nouvelle année", "2026-01-21T00:00:00.000Z",
            "Entraînement pour le club de Mauvezin. Nous vous présentons nos meilleurs vœux pour cette nouvelle année ! Faites du sport, c'est bon pour la santé ! À bientôt !",
            likes=10, comments=0),
        pub("Nouvelle photo de couverture (équipe)", "2025-12-17T00:00:00.000Z",
            "Changement de photo de couverture — photo d'équipe au gymnase.",
            likes=7, comments=1),
        pub("Partage bulletin municipal n°11", "2025-12-17T00:00:00.000Z",
            "Partage du bulletin municipal de Mauvezin n°11 (décembre 2025), section Commission Sport/Jeunesse mentionnant le VCM — créneaux mardi 20h30-22h et samedi 10h-12h au gymnase du collège (horaires de l'époque, saison 2025-2026).",
            likes=3, shares=1),
        pub("Révélation du logo Les Canards Flambés", "2025-12-17T00:00:00.000Z",
            "Changement de photo de profil — révélation du logo du club, Les Canards Flambés.",
            likes=3),
        pub("Nouveau matériel : ballon et sifflet", "2025-11-30T00:00:00.000Z",
            "Changement de photo de profil — photo d'un ballon Molten et d'un sifflet.",
            likes=2, shares=2),
    ]

    print(f"{len(PUBLICATIONS)} publications à créer :")
    for x in PUBLICATIONS:
        print(f"  - {x['fields']['Date/heure de publication'][:10]}  {x['fields']['Titre']}")

    if not WRITE:
        print("\nDry-run terminé. Relance avec --write pour écrire réellement.")
        return

    for i in range(0, len(PUBLICATIONS), 10):
        airtable_request("Publications", "POST", {"records": PUBLICATIONS[i : i + 10]})
    print(f"\n{len(PUBLICATIONS)} publications créées.")


if __name__ == "__main__":
    main()
