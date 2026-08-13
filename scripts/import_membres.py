#!/usr/bin/env python3
"""
Importe les membres actuels du club (fichier Excel) dans la table Membres d'Airtable,
et crée une ligne Adhésions (saison 2025/2026) par membre à partir des colonnes
de cotisation déjà présentes dans le fichier.

En Python (pas Node) volontairement : le paquet npm "xlsx" a deux failles connues
sans correctif publié sur le registre npm (prototype pollution + ReDoS). openpyxl
n'a pas cet historique et est déjà bien maintenu.

Usage :
    python scripts/import_membres.py                 # dry-run : affiche ce qui serait importé
    python scripts/import_membres.py --write          # importe réellement dans Airtable

Prérequis : AIRTABLE_TOKEN et AIRTABLE_BASE_ID dans un fichier .env (voir .env.example),
et le schéma déjà construit (scripts/provision.js) avant de lancer cet import.
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

import openpyxl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # évite les accents mal affichés sur console Windows

ROOT = Path(__file__).resolve().parent.parent
SOURCE_XLSX = ROOT.parent / "VOLLEY CLUB MAUVEZIN 2025-2026.xlsx"
SEASON = "2025/2026"

# Rôles connus au bureau (au-delà du défaut "Joueur") — cf. DM_VCM.md.
# Note : la liste de choix "Rôle(s) au club" définie dans vcm_schema.json ne contient que
# "Président" (pas de variante genrée) — Airtable single/multi-select n'a pas de genre
# grammatical, on garde donc "Président" tel que défini dans le schéma pour Isabelle Devis.
KNOWN_ROLES = {
    ("DEVIS", "ISABELLE"): ["Président", "Joueur"],
    ("FRAPPESAUCE", "YANN"): ["Trésorier", "Joueur"],
}

PAYMENT_MODE_MAP = {
    "VIREMENT": "Virement",
    "ESPECE": "Espèces",
    "ESPECES": "Espèces",
    "CHEQUE": "Chèque",
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


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
    try:
        with urllib.request.urlopen(req) as resp:
            time.sleep(0.25)
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Airtable API {method} {table} -> {e.code}: {e.read().decode('utf-8')}") from e


def payment_mode(raw) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().upper()
    return PAYMENT_MODE_MAP.get(text, "Chèque" if text else None)  # un numéro de chèque tombe ici


def cheque_number(raw) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if text.upper() in PAYMENT_MODE_MAP:
        return None  # c'était un mode de paiement, pas un numéro
    return text


def read_members():
    wb = openpyxl.load_workbook(SOURCE_XLSX, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=3, values_only=True))
    members = []
    anomalies = []
    seen = set()

    for i, row in enumerate(rows, start=3):
        nom = row[0]
        if not nom:
            continue  # ligne de totaux ou vide, fin des données membres
        prenom, naissance, _, lieu_naissance, sexe, adresse, cp, ville, email, tel, debut_adh = row[1:12]
        num_cheque_vcm, montant_vcm, num_cheque_fr, montant_fr, depose = row[13:18]

        key = (str(nom).strip().upper(), str(prenom or "").strip().upper())
        if key in seen:
            anomalies.append(f"Ligne {i} : doublon nom+prénom ({nom} {prenom})")
        seen.add(key)

        for field_name, value in [("Nom", nom), ("Prénom", prenom), ("Adresse", adresse), ("Ville", ville)]:
            if value and "�" in str(value):
                anomalies.append(f"Ligne {i} : caractère mal encodé dans {field_name} ({value!r}) — à corriger à la main")

        if not email:
            anomalies.append(f"Ligne {i} : email manquant ({nom} {prenom})")

        roles = KNOWN_ROLES.get(key, ["Joueur"])

        membre_fields = {
            "Nom": str(nom).strip().title(),
            "Prénom": str(prenom or "").strip().title(),
            "Lieu de naissance": (str(lieu_naissance).strip().title() if lieu_naissance else None),
            "Sexe": {"F": "Femme", "M": "Homme"}.get(str(sexe or "").strip().upper()),
            "Adresse": str(adresse).strip() if adresse else None,
            "Code postal": str(int(cp)) if isinstance(cp, (int, float)) else (str(cp).strip() if cp else None),
            "Ville": str(ville).strip().title() if ville else None,
            "Email": str(email).strip() if email else None,
            "Téléphone": str(tel).strip() if tel else None,
            "Rôle(s) au club": roles,
            "Statut": "Actif",
        }
        if isinstance(naissance, datetime.datetime):
            membre_fields["Date de naissance"] = naissance.date().isoformat()
        membre_fields = {k: v for k, v in membre_fields.items() if v is not None}

        commentaire_bits = []
        if cheque_number(num_cheque_vcm):
            commentaire_bits.append(f"Chèque club n°{cheque_number(num_cheque_vcm)}")
        if cheque_number(num_cheque_fr):
            commentaire_bits.append(f"Chèque Foyer Rural n°{cheque_number(num_cheque_fr)}")
        if depose:
            commentaire_bits.append(f"Chèque déposé : {depose}")

        adhesion_fields = {
            "Saison": SEASON,
            "Adhésion Volley Club Mauvezin": "Validée" if montant_vcm else "À faire",
            "Montant cotisation Club (€)": montant_vcm,
            "Adhésion Foyer Rural": "Validée" if montant_fr else "À faire",
            "Montant Foyer Rural (€)": montant_fr,
            "Mode de paiement": payment_mode(num_cheque_vcm),
            "Commentaire": " ; ".join(commentaire_bits) or None,
        }
        if isinstance(debut_adh, datetime.datetime):
            adhesion_fields["Date paiement Club"] = debut_adh.date().isoformat()
            adhesion_fields["Date paiement Foyer Rural"] = debut_adh.date().isoformat()
        adhesion_fields = {k: v for k, v in adhesion_fields.items() if v is not None}

        members.append({"row": i, "membre": membre_fields, "adhesion": adhesion_fields})

    return members, anomalies


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def main():
    if not SOURCE_XLSX.exists():
        print(f"Fichier introuvable : {SOURCE_XLSX}")
        sys.exit(1)

    members, anomalies = read_members()

    print(f"{len(members)} membres lus dans {SOURCE_XLSX.name}\n")
    for m in members:
        print(f"  - {m['membre']['Nom']} {m['membre']['Prénom']}")

    if anomalies:
        print(f"\n{len(anomalies)} point(s) à vérifier :")
        for a in anomalies:
            print(f"  ! {a}")

    if not WRITE:
        print("\nDry-run (rien n'a été écrit dans Airtable). Relance avec --write pour importer réellement.")
        return

    if not TOKEN or not BASE_ID:
        print("Il manque AIRTABLE_TOKEN et/ou AIRTABLE_BASE_ID (fichier .env ou variables d'environnement).")
        sys.exit(1)

    print("\nImport dans Airtable...")
    created_membres = []
    for batch in chunked(members, 10):
        resp = airtable_request(
            "Membres", "POST", {"records": [{"fields": m["membre"]} for m in batch]}
        )
        created_membres.extend(zip(batch, resp["records"]))

    adhesion_records = []
    for m, rec in created_membres:
        fields = dict(m["adhesion"])
        fields["Membre"] = [rec["id"]]
        adhesion_records.append(fields)

    for batch in chunked(adhesion_records, 10):
        airtable_request("Adhésions", "POST", {"records": [{"fields": f} for f in batch]})

    print(f"\n{len(created_membres)} membres + {len(adhesion_records)} adhésions créés dans Airtable.")
    print("Relecture manuelle recommandée dans Airtable avant d'activer les comptes (cf. GUIDE_VCM_AIRTABLE.md).")


if __name__ == "__main__":
    main()
