#!/usr/bin/env node
/**
 * Entretien automatique de la table Galerie, pensé pour tourner via GitHub Actions (cron) :
 *
 * 1. Supprime les doublons exacts (même photo envoyée plusieurs fois, ex. double-clic sur le
 *    formulaire public) — détectés par hash SHA-256 du contenu du fichier, pas par nom, pour
 *    ne jamais supprimer deux photos différentes qui se ressembleraient. Le plus ancien
 *    enregistrement (createdTime le plus petit) est conservé.
 * 2. Remplit le champ "Date" à partir des métadonnées EXIF (date de prise de vue) des photos
 *    restantes qui n'ont pas encore de Date renseignée.
 *
 * Contourne le fait que l'action "Exécuter un script" d'Airtable est réservée au forfait
 * payant Team — voir ETAT_PROJET_APP_AIRTABLE.md pour le contexte.
 *
 * Usage :
 *   AIRTABLE_TOKEN=xxx AIRTABLE_BASE_ID=appXXXXXXXX node scripts/sync_exif_dates.js
 * ou via un fichier .env local (voir provision.js pour le format).
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const exifr = require("exifr");

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const content = fs.readFileSync(filePath, "utf8");
  for (const rawLine of content.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

loadEnvFile(path.join(__dirname, "..", ".env"));

const TOKEN = process.env.AIRTABLE_TOKEN;
const BASE_ID = process.env.AIRTABLE_BASE_ID;

if (!TOKEN || !BASE_ID) {
  console.error("Il manque AIRTABLE_TOKEN et/ou AIRTABLE_BASE_ID.");
  process.exit(1);
}

const API_ROOT = `https://api.airtable.com/v0/${BASE_ID}`;
const headers = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };

function toIsoDate(d) {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

async function fetchAllGalerieWithPhoto() {
  const filter = encodeURIComponent("NOT({Fichiers} = BLANK())");
  const res = await fetch(`${API_ROOT}/Galerie?filterByFormula=${filter}`, { headers });
  if (!res.ok) {
    throw new Error(`Erreur lecture Galerie: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return data.records || [];
}

async function deleteRecords(ids) {
  for (let i = 0; i < ids.length; i += 10) {
    const batch = ids.slice(i, i + 10);
    const qs = batch.map((id) => `records[]=${id}`).join("&");
    const res = await fetch(`${API_ROOT}/Galerie?${qs}`, { method: "DELETE", headers });
    if (!res.ok) {
      console.error("  Échec suppression doublons:", res.status, await res.text());
    }
  }
}

async function main() {
  const records = await fetchAllGalerieWithPhoto();
  console.log(`${records.length} photo(s) au total à examiner.`);

  // Télécharge chaque photo une seule fois, sert à la fois au hash (doublons) et à l'EXIF.
  const withBuffer = [];
  for (const record of records) {
    const attachment = record.fields["Fichiers"][0];
    try {
      const imgRes = await fetch(attachment.url);
      const buffer = Buffer.from(await imgRes.arrayBuffer());
      const hash = crypto.createHash("sha256").update(buffer).digest("hex");
      withBuffer.push({ record, buffer, hash });
    } catch (e) {
      console.error(`  ${record.id} : échec téléchargement -`, e.message);
    }
  }

  // --- 1. Doublons : même hash de contenu -> on garde le plus ancien, on supprime le reste.
  const byHash = new Map();
  for (const item of withBuffer) {
    if (!byHash.has(item.hash)) byHash.set(item.hash, []);
    byHash.get(item.hash).push(item);
  }

  const toDeleteIds = [];
  const survivors = [];
  for (const group of byHash.values()) {
    if (group.length === 1) {
      survivors.push(group[0]);
      continue;
    }
    group.sort((a, b) => new Date(a.record.createdTime) - new Date(b.record.createdTime));
    const [keep, ...duplicates] = group;
    survivors.push(keep);
    for (const dup of duplicates) {
      console.log(`  Doublon détecté : ${dup.record.id} (identique à ${keep.record.id}), suppression.`);
      toDeleteIds.push(dup.record.id);
    }
  }
  if (toDeleteIds.length > 0) {
    await deleteRecords(toDeleteIds);
  }
  console.log(`${toDeleteIds.length} doublon(s) supprimé(s).`);

  // --- 2. Date EXIF pour les survivants qui n'en ont pas encore.
  let updated = 0;
  let skipped = 0;

  for (const { record, buffer } of survivors) {
    if (record.fields["Date"]) {
      continue; // déjà renseignée, on ne l'écrase pas
    }
    try {
      const exifData = await exifr.parse(buffer, { pick: ["DateTimeOriginal", "CreateDate"] });
      const takenAt = exifData && (exifData.DateTimeOriginal || exifData.CreateDate);
      if (!takenAt) {
        console.log(`  ${record.id} : pas de date EXIF trouvée, ignoré.`);
        skipped++;
        continue;
      }

      const isoDate = toIsoDate(new Date(takenAt));
      const patchRes = await fetch(`${API_ROOT}/Galerie/${record.id}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ fields: { Date: isoDate } }),
      });
      if (!patchRes.ok) {
        console.error(`  ${record.id} : échec mise à jour -`, patchRes.status, await patchRes.text());
        continue;
      }
      console.log(`  ${record.id} : Date -> ${isoDate}`);
      updated++;
    } catch (e) {
      console.error(`  ${record.id} : erreur -`, e.message);
      skipped++;
    }
  }

  console.log(`Terminé : ${updated} date(s) mise(s) à jour, ${skipped} ignorée(s)/en erreur.`);
}

main().catch((e) => {
  console.error("Erreur fatale :", e.message);
  process.exit(1);
});
