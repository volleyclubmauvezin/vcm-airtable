# VCM — Airtable (scripts de provisioning)

Construit et alimente la base Airtable de gestion du Volley Club Mauvezin à partir d'une
spec versionnée, plutôt qu'à la main champ par champ. Voir `../GUIDE_VCM_AIRTABLE.md` pour
le mode d'emploi côté club (ajouter un membre, archivage annuel, etc.) — ce README est la
doc technique des scripts eux-mêmes.

## Contenu

- `schema/vcm_schema.json` — les 17 tables du club (champs, types, relations), source de vérité du schéma.
- `scripts/provision.js` — construit tables/champs/relations dans une base Airtable vide, via l'API Metadata. Node, aucune dépendance.
- `scripts/import_membres.py` — importe les membres actuels (fichier Excel) + crée leur ligne Adhésions saison 2025/2026. Python + openpyxl.

## Mise en place (une fois)

1. **Créer la base Airtable** : dans le compte `volleyclubmauvezin@gmail.com`, "Add a base" > "Start from scratch", nommer par exemple "VCM — Gestion". Laisser vide (les 17 tables seront créées par le script).
2. **Générer un Personal Access Token** : Paramètres du compte > Developer hub > Personal access tokens > Create token. Scopes : `data.records:read`, `data.records:write`, `schema.bases:read`, `schema.bases:write`. Accès : la base créée à l'étape 1 uniquement.
3. **Copier `.env.example` en `.env`** et renseigner `AIRTABLE_TOKEN` (le token ci-dessus) et `AIRTABLE_BASE_ID` (visible dans l'URL de la base : `airtable.com/appXXXXXXXXXXXXXX/...`).
4. **Installer les dépendances Python** (le script d'import) : `pip install -r requirements.txt`. Le script de provisioning (Node) n'a besoin d'aucune installation.

## Utilisation

```bash
# 1) Construire le schéma (17 tables, champs, relations, formules) — idempotent, peut être relancé sans risque
node scripts/provision.js

# 2) Vérifier dans Airtable les 1-2 champs listés comme "à ajouter à la main" en fin d'exécution
#    (rollup Matériel.Quantité dispo — voir GUIDE_VCM_AIRTABLE.md)

# 3) Importer les membres actuels — dry-run d'abord (n'écrit rien, affiche juste ce qui serait fait)
python scripts/import_membres.py
# puis, une fois vérifié :
python scripts/import_membres.py --write
```

## Réutiliser pour un autre club

Le script est générique : pointé (via `.env`) vers la base Airtable vide d'une autre association,
`node scripts/provision.js` reconstruit le même schéma en quelques minutes. Adapter ensuite les
listes de choix (single/multiSelect) de `vcm_schema.json` si besoin (ex. rôles, catégories).
