#!/usr/bin/env python3
"""
Script ponctuel (one-off) : importe les opérations bancaires réelles du compte courant
VCM (février-août 2026), transcrites depuis les captures d'écran de l'appli bancaire,
avec les précisions apportées par le trésorier sur les lignes ambiguës (chèques émis,
virement de remboursement matériel).

Usage :
    python scripts/seed_transactions_2026.py          # dry-run
    python scripts/seed_transactions_2026.py --write   # écrit réellement dans Airtable
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
    url = f"https://api.airtable.com/v0/{BASE_ID}/{urllib.parse.quote(table)}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        time.sleep(0.25)
        return json.loads(resp.read().decode("utf-8"))


def t(date, type_, categorie, montant, mode, beneficiaire=None, commentaire=None, sous_categorie=None):
    fields = {
        "Date": date,
        "Type": type_,
        "Catégorie": categorie,
        "Montant (€)": montant,
        "Mode paiement": mode,
    }
    if beneficiaire:
        fields["Bénéficiaire / Payeur"] = beneficiaire
    if commentaire:
        fields["Commentaire"] = commentaire
    if sous_categorie:
        fields["Sous-catégorie"] = sous_categorie
    return {"fields": fields}


TRANSACTIONS = [
    t("2026-02-05", "Recette", "Cotisations", 600.00, "Chèque", "Dépôt cotisations (lot de chèques)"),
    t("2026-02-05", "Recette", "Cotisations", 80.00, "Espèces", "Dépôt cotisations (espèces)"),
    t("2026-02-06", "Recette", "Cotisations", 40.00, "Virement", commentaire="Virement adhérent - COTISATION 2025 2026"),
    t("2026-02-06", "Recette", "Cotisations", 40.00, "Virement", "Yann Frappesauce"),
    t("2026-02-10", "Dépense", "Frais fonctionnement", 6.70, "Autre", sous_categorie="Frais virement SEPA occasionnel"),
    t("2026-02-10", "Recette", "Cotisations", 40.00, "Virement", "Guillaume Ludger"),
    t("2026-02-10", "Dépense", "Achats matériel", 469.17, "Virement", "Yann Frappesauce (remboursement)",
      commentaire="Remboursement : enceinte Zealot S89, 8 ballons volley d'occasion, sac à ballons, sifflet poire — à confirmer avec justificatifs papier"),
    t("2026-02-16", "Dépense", "Frais fonctionnement", 3.50, "Autre", sous_categorie="Tenue de compte professionnel"),
    t("2026-02-25", "Dépense", "Frais fonctionnement", 20.00, "Autre", sous_categorie="Part sociale (souscription)"),
    t("2026-02-25", "Recette", "Frais fonctionnement", 3.50, "Autre", sous_categorie="Rétrocession bancaire (tenue de compte)"),
    t("2026-02-25", "Recette", "Frais fonctionnement", 6.70, "Autre", sous_categorie="Rétrocession bancaire (virement SEPA)"),
    t("2026-03-03", "Dépense", "Frais fonctionnement", 1.35, "Autre", sous_categorie="Envoi de chéquier"),
    t("2026-03-06", "Dépense", "Frais fonctionnement", 1.70, "Autre", sous_categorie="CAEL pro niveau intermédiaire"),
    t("2026-03-10", "Recette", "Cotisations", 25.00, "Chèque", "Dépôt cotisations (chèque)"),
    t("2026-03-11", "Recette", "Cotisations", 50.00, "Espèces", "Dépôt cotisations (espèces)"),
    t("2026-03-16", "Dépense", "Frais fonctionnement", 2.00, "Autre", sous_categorie="Tenue de compte professionnel"),
    t("2026-04-08", "Dépense", "Frais fonctionnement", 1.70, "Autre", sous_categorie="CAEL pro niveau intermédiaire"),
    t("2026-04-13", "Dépense", "Événement", 91.00, "Chèque",
      commentaire="Grillades et pain — Fête du club juin 2026 (à confirmer, date d'achat antérieure à l'événement)"),
    t("2026-04-17", "Dépense", "Frais fonctionnement", 2.00, "Autre", sous_categorie="Tenue de compte professionnel"),
    t("2026-05-07", "Dépense", "Frais fonctionnement", 1.70, "Autre", sous_categorie="CAEL pro niveau intermédiaire"),
    t("2026-05-16", "Dépense", "Frais fonctionnement", 2.00, "Autre", sous_categorie="Tenue de compte professionnel"),
    t("2026-06-09", "Dépense", "Frais fonctionnement", 1.70, "Autre", sous_categorie="CAEL pro niveau intermédiaire"),
    t("2026-06-16", "Dépense", "Frais fonctionnement", 2.00, "Autre", sous_categorie="Tenue de compte professionnel"),
    t("2026-07-02", "Dépense", "Événement", 62.65, "Chèque",
      commentaire="Grillades et pain — Fête du club juin 2026 (à confirmer)"),
    t("2026-07-07", "Dépense", "Frais fonctionnement", 1.70, "Autre", sous_categorie="CAEL pro niveau intermédiaire"),
    t("2026-07-16", "Dépense", "Frais fonctionnement", 2.00, "Autre", sous_categorie="Tenue de compte professionnel"),
    t("2026-07-28", "Recette", "Subvention", 1000.00, "Virement", "DDFIP Hérault", sous_categorie="FDVA2 2026"),
    t("2026-08-04", "Dépense", "Achats matériel", 179.98, "Chèque",
      commentaire="Remboursement achat 2 kits filet + poteaux (Décathlon) — bénéficiaire à préciser"),
    t("2026-08-07", "Dépense", "Frais fonctionnement", 1.70, "Autre", sous_categorie="CAEL pro niveau intermédiaire"),
]


def main():
    total_recettes = sum(x["fields"]["Montant (€)"] for x in TRANSACTIONS if x["fields"]["Type"] == "Recette")
    total_depenses = sum(x["fields"]["Montant (€)"] for x in TRANSACTIONS if x["fields"]["Type"] == "Dépense")
    print(f"{len(TRANSACTIONS)} transactions à créer — mode : {'ÉCRITURE' if WRITE else 'dry-run'}")
    print(f"Total recettes : {total_recettes:.2f} € — Total dépenses : {total_depenses:.2f} € — Net : {total_recettes - total_depenses:.2f} €\n")
    for tx in TRANSACTIONS:
        f = tx["fields"]
        signe = "+" if f["Type"] == "Recette" else "-"
        print(f"  {f['Date']}  {signe}{f['Montant (€)']:.2f}€  {f['Catégorie']:<18} {f.get('Bénéficiaire / Payeur', f.get('Sous-catégorie', ''))}")

    if not WRITE:
        print("\nDry-run terminé (rien n'a été écrit). Relance avec --write pour importer réellement.")
        return

    if not TOKEN or not BASE_ID:
        print("Il manque AIRTABLE_TOKEN / AIRTABLE_BASE_ID.")
        sys.exit(1)

    for i in range(0, len(TRANSACTIONS), 10):
        batch = TRANSACTIONS[i : i + 10]
        airtable_request("Transactions", "POST", {"records": batch})
    print(f"\n{len(TRANSACTIONS)} transactions créées dans Airtable.")


if __name__ == "__main__":
    main()
