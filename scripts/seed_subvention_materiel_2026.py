#!/usr/bin/env python3
"""
Script ponctuel : ajoute la subvention FDVA2 2026 (confirmée par l'arrêté officiel DRAJES
Occitanie du 06/07/2026, 020_DEMANDE SUBVENTIONS/2026_FDVA/DD32-26-0312-...pdf) et le
matériel connu du club (ballons, enceinte, filets/poteaux), puis relie la transaction
bancaire du 28/07/2026 (+1000€ DDFIP Hérault) à cette subvention.

Usage :
    python scripts/seed_subvention_materiel_2026.py          # dry-run
    python scripts/seed_subvention_materiel_2026.py --write   # écrit réellement
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


SUBVENTION = {
    "fields": {
        "Organisme": "DRAJES Occitanie (Direction de région académique à la jeunesse, à l'engagement et aux sports)",
        "Objet": "FDVA2 2026 — Financement global : structuration et développement du VCM, organisation d'événements sportifs",
        "Montant demandé (€)": 3000,
        "Montant obtenu (€)": 1000,
        "Date demande": "2026-03-05",
        "Date réponse": "2026-07-06",
        "Statut": "Acceptée",
        "Notes": (
            "Dossier DD32-26-0312 / 26-059874. Versement unique reçu le 28/07/2026 (virement "
            "DDFIP Hérault, cf. Transactions). Date de demande estimée d'après la date de "
            "finalisation du dossier (05/03/2026) — à ajuster si la date réelle de dépôt en "
            "ligne diffère. Compte rendu financier à saisir sur \"lecompteasso\" en fin d'action "
            "(31/12/2026 au plus tard, obligation de l'arrêté)."
        ),
    }
}

MATERIEL = [
    {
        "fields": {
            "Référence": "Ballons de volley (achat initial)",
            "Catégorie": "Ballon",
            "État": "Bon",
            "Valeur estimée (€)": 450,
            "Date achat": "2025-09-15",
            "Notes": "Achat initial du club (~450€), septembre 2025 — premier équipement propre, avant poteaux/filets.",
        }
    },
    {
        "fields": {
            "Référence": "8 ballons de volley d'occasion",
            "Catégorie": "Ballon",
            "Quantité totale": 8,
            "État": "Bon",
            "Date achat": "2026-02-10",
            "Notes": "Achat d'occasion, remboursé groupé avec enceinte/sac/sifflet (469,17€ le 10/02/2026) — détail des prix par article à préciser avec les justificatifs papier.",
        }
    },
    {
        "fields": {
            "Référence": "Enceinte Zealot S89",
            "Catégorie": "Enceinte",
            "Quantité totale": 1,
            "État": "Neuf",
            "Date achat": "2026-02-10",
            "Notes": "Remboursée groupée avec les 8 ballons/sac/sifflet (469,17€ le 10/02/2026) — prix à préciser.",
        }
    },
    {
        "fields": {
            "Référence": "Sac à ballons",
            "Catégorie": "Autre",
            "Quantité totale": 1,
            "État": "Neuf",
            "Date achat": "2026-02-10",
            "Notes": "Remboursé groupé avec enceinte/ballons/sifflet (469,17€ le 10/02/2026) — prix à préciser.",
        }
    },
    {
        "fields": {
            "Référence": "Sifflet poire",
            "Catégorie": "Autre",
            "Quantité totale": 1,
            "État": "Neuf",
            "Date achat": "2026-02-10",
            "Notes": "Remboursé groupé avec enceinte/ballons/sac (469,17€ le 10/02/2026) — prix à préciser.",
        }
    },
    {
        "fields": {
            "Référence": "2 kits poteaux + filet (Décathlon)",
            "Catégorie": "Filet",
            "Quantité totale": 2,
            "État": "Neuf",
            "Valeur estimée (€)": 179.98,
            "Date achat": "2026-08-04",
            "Notes": "Remboursement 179,98€ (chèque émis 04/08/2026) — bénéficiaire du remboursement à préciser. Date d'achat réelle possiblement antérieure au chèque.",
        }
    },
]


def main():
    print(f"Mode : {'ÉCRITURE' if WRITE else 'dry-run'}\n")
    print("Subvention à créer :")
    print(f"  - {SUBVENTION['fields']['Objet']} : {SUBVENTION['fields']['Montant obtenu (€)']}€ obtenus sur {SUBVENTION['fields']['Montant demandé (€)']}€ demandés")
    print(f"\n{len(MATERIEL)} matériels à créer :")
    for m in MATERIEL:
        print(f"  - {m['fields']['Référence']}")

    if not WRITE:
        print("\nDry-run terminé (rien n'a été écrit). Relance avec --write pour écrire réellement.")
        return

    if not TOKEN or not BASE_ID:
        print("Il manque AIRTABLE_TOKEN / AIRTABLE_BASE_ID.")
        sys.exit(1)

    sub_resp = airtable_request("Subventions", "POST", {"records": [SUBVENTION]})
    subvention_id = sub_resp["records"][0]["id"]
    print(f"\nSubvention créée : {subvention_id}")

    mat_resp = airtable_request("Matériel", "POST", {"records": MATERIEL})
    print(f"{len(mat_resp['records'])} matériels créés.")

    # Relie la transaction DDFIP Hérault (+1000€, 28/07/2026) à cette subvention
    tx = airtable_request(
        "Transactions?" + urllib.parse.urlencode({"filterByFormula": '{Bénéficiaire / Payeur}="DDFIP Hérault"'}),
        "GET",
    )
    if tx["records"]:
        tx_id = tx["records"][0]["id"]
        airtable_request(f"Transactions/{tx_id}", "PATCH", {"fields": {"Lien subvention": [subvention_id]}})
        print(f"Transaction {tx_id} reliée à la subvention.")
    else:
        print("Transaction DDFIP Hérault introuvable — lien non créé (à faire à la main si besoin).")


if __name__ == "__main__":
    main()
