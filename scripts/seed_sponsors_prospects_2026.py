#!/usr/bin/env python3
"""
Script ponctuel : importe la liste des cibles de prospection sponsors du tournoi sur
gazon (TOURNOI/KIT_SPONSORS_TOURNOI_VCM.md, section 5) comme prospects dans la table
Sponsors — aucun partenariat n'est confirmé à ce stade, tout est "à contacter".

Usage :
    python scripts/seed_sponsors_prospects_2026.py          # dry-run
    python scripts/seed_sponsors_prospects_2026.py --write   # écrit réellement
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


def p(nom, angle, niveau, responsable, extra=None):
    contreparties = f"Niveau visé : {niveau}. Angle : {angle}."
    if extra:
        contreparties += f" {extra}"
    return {
        "fields": {
            "Nom": nom,
            "Contact": f"Responsable club : {responsable} (prospection tournoi sur gazon 4 octobre 2026)",
            "Contreparties": contreparties,
            "Statut": "Prospect",
        }
    }


PROSPECTS = [
    p("Decathlon Auch/Fleurance", "Geste initial déjà fait (2 bons de 10€ à l'achat des kits volley) — formaliser en partenaire matériel + lots", "Partenaire", "Yann",
      "Déjà un premier contact positif : a offert 2 bons de 10€ à l'achat des 2 kits volley. Prioritaire."),
    p("Boucherie Cenevese Mauvezin", "Pressenti pour viande buvette + logo — déjà mentionné sur une maquette d'affiche non diffusée, à formaliser avant toute publication", "Ami/Partenaire", "Isabelle"),
    p("Le Billot des Abattoirs Mauvezin", "Pressenti, même angle que Boucherie Cenevese — déjà mentionné sur une maquette non diffusée, à formaliser avant publication", "Ami/Partenaire", "Isabelle"),
    p("Boulangerie Mauvezin", "Sandwiches/casse-croûtes pour la buvette du tournoi", "Ami", "Isabelle"),
    p("Intermarché ou Super U Mauvezin", "Boissons + épicerie pour la buvette", "Partenaire", "Yann"),
    p("Crédit Agricole Pyrénées Gascogne", "Banque du club (RIB) — sponsoring classique, courrier officiel", "Partenaire", "Yann"),
    p("Groupama / MAIF", "Assurance club — mécénat sport-association, courrier officiel", "Ami/Partenaire", "Yann"),
    p("Communauté de communes Bastides de Lomagne", "Institutionnel — soutien logistique/dotation", "Ami", "Isabelle"),
    p("Mairie de Mauvezin", "Soutien technique + éventuel financier", "Ami", "Isabelle"),
    p("Pharmacies Mauvezin", "Trousse de secours + dotation santé (2 pharmacies à Mauvezin)", "Ami", "Isabelle"),
    p("Restaurants Mauvezin", "Lots + repas bénévoles — responsable à nommer", "Ami", "À nommer"),
    p("Garage local Mauvezin", "Sponsoring général — responsable à nommer", "Ami", "À nommer"),
    p("Coiffeur / institut Mauvezin", "Lots pour tirage au sort — responsable à nommer", "Ami", "À nommer"),
    p("Domaine Côtes de Gascogne local", "Apéro remise des prix — responsable à nommer", "Ami", "À nommer"),
    p("Producteur foie gras / conserverie local", "Lots gagnants — responsable à nommer", "Ami", "À nommer"),
]


def main():
    print(f"{len(PROSPECTS)} prospects sponsors à créer — mode : {'ÉCRITURE' if WRITE else 'dry-run'}\n")
    for x in PROSPECTS:
        print(f"  - {x['fields']['Nom']}")

    if not WRITE:
        print("\nDry-run terminé. Relance avec --write pour écrire réellement.")
        return

    if not TOKEN or not BASE_ID:
        print("Il manque AIRTABLE_TOKEN / AIRTABLE_BASE_ID.")
        sys.exit(1)

    for i in range(0, len(PROSPECTS), 10):
        airtable_request("Sponsors", "POST", {"records": PROSPECTS[i : i + 10]})
    print(f"\n{len(PROSPECTS)} prospects créés dans Sponsors.")


if __name__ == "__main__":
    main()
