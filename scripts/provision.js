#!/usr/bin/env node
/**
 * Construit le schéma Airtable du club (17 tables) à partir de schema/vcm_schema.json,
 * via l'API Metadata Airtable. Idempotent : peut être relancé sans dupliquer ce qui existe déjà.
 *
 * Usage :
 *   AIRTABLE_TOKEN=xxx AIRTABLE_BASE_ID=appXXXXXXXX node scripts/provision.js
 * ou en créant un fichier .env (voir .env.example) à côté de ce script.
 *
 * Prérequis : une base Airtable VIDE déjà créée à la main dans l'UI (Add a base > Start from
 * scratch), avec au moins un token d'accès personnel ayant les scopes data.records:read/write
 * et schema.bases:read/write, autorisé sur cette base.
 */

const fs = require("fs");
const path = require("path");

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
  console.error(
    "Il manque AIRTABLE_TOKEN et/ou AIRTABLE_BASE_ID. Renseigne-les dans un fichier .env " +
      "(copie .env.example) ou en variables d'environnement avant de lancer ce script."
  );
  process.exit(1);
}

const API_ROOT = `https://api.airtable.com/v0/meta/bases/${BASE_ID}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function airtableFetch(pathSuffix, options = {}) {
  const res = await fetch(`${API_ROOT}${pathSuffix}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { raw: text };
  }
  if (!res.ok) {
    const err = new Error(
      `Airtable API ${options.method || "GET"} ${pathSuffix} -> ${res.status}: ${JSON.stringify(body)}`
    );
    err.status = res.status;
    err.body = body;
    throw err;
  }
  await sleep(250); // reste large sous la limite Airtable (~5 req/s par base)
  return body;
}

async function getSchema() {
  const data = await airtableFetch("/tables");
  const byName = {};
  for (const t of data.tables) {
    byName[t.name] = {
      id: t.id,
      fields: Object.fromEntries(t.fields.map((f) => [f.name, f.id])),
    };
  }
  return byName;
}

async function createTable(tableSpec) {
  const fields = [
    tableSpec.primaryField,
    ...(tableSpec.fields || []),
  ];
  console.log(`  Création de la table "${tableSpec.name}" (${fields.length} champs de base)...`);
  return airtableFetch("/tables", {
    method: "POST",
    body: JSON.stringify({ name: tableSpec.name, fields }),
  });
}

async function createField(tableId, fieldSpec) {
  return airtableFetch(`/tables/${tableId}/fields`, {
    method: "POST",
    body: JSON.stringify(fieldSpec),
  });
}

async function renameField(tableId, fieldId, newName) {
  return airtableFetch(`/tables/${tableId}/fields/${fieldId}`, {
    method: "PATCH",
    body: JSON.stringify({ name: newName }),
  });
}

async function main() {
  const schemaSpec = JSON.parse(
    fs.readFileSync(path.join(__dirname, "..", "schema", "vcm_schema.json"), "utf8")
  );

  console.log("Étape 1/6 — Lecture du schéma existant sur Airtable...");
  let live = await getSchema();

  console.log("\nÉtape 2/6 — Création des tables et champs de base...");
  for (const table of schemaSpec.tables) {
    if (live[table.name]) {
      console.log(`  "${table.name}" existe déjà, on passe.`);
      continue;
    }
    try {
      await createTable(table);
    } catch (e) {
      console.error(`  Échec création table "${table.name}": ${e.message}`);
    }
  }
  live = await getSchema();

  console.log("\nÉtape 3/6 — Création des champs de lien (avec renommage du champ inverse)...");
  for (const table of schemaSpec.tables) {
    const tableInfo = live[table.name];
    if (!tableInfo) {
      console.error(`  Table "${table.name}" introuvable, champs de lien ignorés.`);
      continue;
    }
    for (const link of table.linkFields || []) {
      if (tableInfo.fields[link.name]) {
        console.log(`  ${table.name}.${link.name} existe déjà, on passe.`);
        continue;
      }
      const targetTable = live[link.linkedTable];
      if (!targetTable) {
        console.error(`  Table liée "${link.linkedTable}" introuvable pour ${table.name}.${link.name}.`);
        continue;
      }
      const fieldsBefore = new Set(Object.keys(targetTable.fields));
      try {
        console.log(`  ${table.name}.${link.name} -> ${link.linkedTable}`);
        await createField(tableInfo.id, {
          name: link.name,
          type: "multipleRecordLinks",
          options: { linkedTableId: targetTable.id },
        });
        // Airtable crée automatiquement le champ miroir sur la table liée : on le retrouve
        // en comparant la liste de champs avant/après, puis on le renomme.
        const refreshed = await getSchema();
        live = refreshed;
        const newTargetFields = live[link.linkedTable].fields;
        const newFieldName = Object.keys(newTargetFields).find((n) => !fieldsBefore.has(n));
        if (newFieldName && link.inverseName && newFieldName !== link.inverseName) {
          await renameField(live[link.linkedTable].id, newTargetFields[newFieldName], link.inverseName);
          live = await getSchema();
        } else if (!newFieldName) {
          console.warn(
            `    Attention : champ inverse non détecté automatiquement sur "${link.linkedTable}" ` +
              `pour ${table.name}.${link.name} — à vérifier/renommer à la main si besoin.`
          );
        }
      } catch (e) {
        console.error(`  Échec création lien ${table.name}.${link.name}: ${e.message}`);
      }
    }
  }
  live = await getSchema();

  console.log("\nÉtape 4/6 — Création des champs formule et lookup...");
  for (const table of schemaSpec.tables) {
    const tableInfo = live[table.name];
    if (!tableInfo) continue;

    for (const f of table.formulaFields || []) {
      if (tableInfo.fields[f.name]) {
        console.log(`  ${table.name}.${f.name} existe déjà, on passe.`);
        continue;
      }
      try {
        console.log(`  ${table.name}.${f.name} (formule)`);
        await createField(tableInfo.id, { name: f.name, type: f.type, options: f.options });
      } catch (e) {
        console.error(`  Échec création formule ${table.name}.${f.name}: ${e.message}`);
      }
    }

    for (const lk of table.lookupFields || []) {
      if (tableInfo.fields[lk.name]) {
        console.log(`  ${table.name}.${lk.name} existe déjà, on passe.`);
        continue;
      }
      const linkFieldId = tableInfo.fields[lk.sourceLinkField];
      if (!linkFieldId) {
        console.error(
          `  Impossible de créer le lookup ${table.name}.${lk.name} : champ de lien ` +
            `"${lk.sourceLinkField}" introuvable.`
        );
        continue;
      }
      // Retrouver l'ID du champ source dans la table liée correspondante.
      const linkSpec = (table.linkFields || []).find((l) => l.name === lk.sourceLinkField);
      const linkedTableInfo = linkSpec && live[linkSpec.linkedTable];
      const sourceFieldId = linkedTableInfo && linkedTableInfo.fields[lk.sourceField];
      if (!sourceFieldId) {
        console.error(
          `  Impossible de créer le lookup ${table.name}.${lk.name} : champ source ` +
            `"${lk.sourceField}" introuvable dans la table liée.`
        );
        continue;
      }
      try {
        console.log(`  ${table.name}.${lk.name} (lookup)`);
        await createField(tableInfo.id, {
          name: lk.name,
          type: "multipleLookupValues",
          options: { recordLinkFieldId: linkFieldId, fieldIdInLinkedTable: sourceFieldId },
        });
      } catch (e) {
        console.error(`  Échec création lookup ${table.name}.${lk.name}: ${e.message}`);
      }
    }
  }

  live = await getSchema();

  console.log("\nÉtape 5/6 — Création des champs rollup...");
  // Note : l'API Airtable ne permet pas de filtrer un rollup (contrairement à l'UI). Pour un
  // rollup "conditionnel", le schéma doit prévoir un champ formule intermédiaire dans la table
  // liée (déjà zéroté pour les lignes à exclure) et faire un SUM(values) simple dessus ici.
  for (const table of schemaSpec.tables) {
    const tableInfo = live[table.name];
    if (!tableInfo) continue;
    for (const rf of table.rollupFields || []) {
      if (tableInfo.fields[rf.name]) {
        console.log(`  ${table.name}.${rf.name} existe déjà, on passe.`);
        continue;
      }
      const linkFieldId = tableInfo.fields[rf.sourceLinkField];
      const linkSpec = (table.linkFields || []).find((l) => l.name === rf.sourceLinkField);
      const linkedTableInfo = linkSpec && live[linkSpec.linkedTable];
      const sourceFieldId = linkedTableInfo && linkedTableInfo.fields[rf.sourceField];
      if (!linkFieldId || !sourceFieldId) {
        console.error(
          `  Impossible de créer le rollup ${table.name}.${rf.name} : champ de lien ou champ ` +
            `source introuvable ("${rf.sourceLinkField}" / "${rf.sourceField}").`
        );
        continue;
      }
      try {
        console.log(`  ${table.name}.${rf.name} (rollup)`);
        await createField(tableInfo.id, {
          name: rf.name,
          type: "rollup",
          options: { recordLinkFieldId: linkFieldId, fieldIdInLinkedTable: sourceFieldId, formula: rf.formula },
        });
      } catch (e) {
        console.error(`  Échec création rollup ${table.name}.${rf.name}: ${e.message}`);
      }
    }
  }
  live = await getSchema();

  console.log("\nÉtape 6/6 — Création des champs formule dépendant d'un rollup...");
  for (const table of schemaSpec.tables) {
    const tableInfo = live[table.name];
    if (!tableInfo) continue;
    for (const f of table.postRollupFormulaFields || []) {
      if (tableInfo.fields[f.name]) {
        console.log(`  ${table.name}.${f.name} existe déjà, on passe.`);
        continue;
      }
      try {
        console.log(`  ${table.name}.${f.name} (formule post-rollup)`);
        await createField(tableInfo.id, { name: f.name, type: f.type, options: f.options });
      } catch (e) {
        console.error(`  Échec création formule ${table.name}.${f.name}: ${e.message}`);
      }
    }
  }

  console.log("\nTerminé.");

  const manualNotes = [];
  for (const table of schemaSpec.tables) {
    for (const m of table.manualFields || []) {
      manualNotes.push(`  - ${table.name}.${m.name} : ${m.reason}`);
    }
  }
  if (manualNotes.length) {
    console.log("\nChamps à ajouter à la main dans l'UI Airtable (voir GUIDE_VCM_AIRTABLE.md) :");
    console.log(manualNotes.join("\n"));
  }
  console.log(
    "\nProchaine étape : construire les Interfaces (dashboards) et les Automatisations dans " +
      "l'UI Airtable — non scriptables via l'API publique."
  );
}

main().catch((e) => {
  console.error("\nErreur fatale :", e.message);
  process.exit(1);
});
