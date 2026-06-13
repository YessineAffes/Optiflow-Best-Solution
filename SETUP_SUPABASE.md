# Optiflow Best Solution — Mise en place Supabase & deploiement

Ce guide part de zero : creation du projet Supabase, des tables, recuperation
des cles, configuration locale, puis options de deploiement.

L'app fonctionne **sans** Supabase (mode degrade : pas de produits ni
d'annotations enregistres). Supabase active la base produits et la collecte des
annotations expert.

---

## 1. Creer le projet Supabase

1. Va sur https://supabase.com et cree un compte (gratuit).
2. **New project** → choisis une organisation, un nom (ex: `optiflow`), un mot
   de passe de base de donnees (note-le), et une region proche de tes
   utilisateurs.
3. Attends ~2 min que le projet soit provisionne.

## 2. Creer les tables

1. Dans le projet, ouvre **SQL Editor** (menu de gauche).
2. **New query**, colle tout le contenu de [`supabase_schema.sql`](supabase_schema.sql).
3. Clique **Run**. Tu dois voir « Success ». Cela cree les tables
   `products`, `expert_annotations`, `recommendation_logs` et leurs policies.

## 3. Recuperer les cles

1. Menu **Project Settings** (roue dentee) → **API**.
2. Copie :
   - **Project URL** → `SUPABASE_URL`
   - **Project API keys → `anon` `public`** → `SUPABASE_KEY`

> La cle `anon` suffit pour demarrer (les policies du schema autorisent
> lecture/ecriture). Pour un usage durci, restreins ensuite les policies et
> passe a une cle de service cote serveur uniquement.

## 4. Configurer en local

1. Copie `.env.example` vers `.env` (s'il n'existe pas deja).
2. Renseigne :
   ```
   SUPABASE_URL=https://xxxxxxxx.supabase.co
   SUPABASE_KEY=eyJhbGciOi...   # cle anon public
   ```
3. Installe les dependances :
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Lance l'app :
   ```powershell
   python -m streamlit run app.py
   ```
5. Verifie : page **Produits** (menu de gauche) → ajoute un produit ; il doit
   apparaitre dans la liste, et dans Supabase → **Table editor → products**.
   Active **Mode expert** (sidebar) → une question affiche un bloc « Expert »
   pour saisir note + verification.

---

## 5. Deploiement

Le projet est concu pour etre deployable partout. La seule exigence : fournir
les variables d'environnement `SUPABASE_URL`, `SUPABASE_KEY` (et les `LLM_*`
si tu utilises un LLM). Selon ta cible :

### Option A — Streamlit Community Cloud
1. Pousse le projet sur un repo GitHub.
2. https://share.streamlit.io → **New app** → pointe sur `app.py`.
3. **Advanced settings → Secrets** : colle
   ```toml
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_KEY = "eyJ..."
   ```

### Option B — Hugging Face Spaces (SDK Streamlit)
1. Cree un Space type **Streamlit**, pousse le code.
2. **Settings → Variables and secrets** : ajoute `SUPABASE_URL`, `SUPABASE_KEY`.

### Option C — Docker / VPS
Construis une image a partir de `python:3.12-slim`, installe
`requirements.txt`, expose le port 8501 et lance
`streamlit run app.py --server.port 8501 --server.address 0.0.0.0`.
Passe les secrets via variables d'environnement (`-e SUPABASE_URL=...`).

> Dis-moi ta cible exacte et je fournis le fichier de deploiement precis
> (`Dockerfile`, `.streamlit/secrets.toml`, ou config du Space).

---

## Donnees collectees

| Table | Contenu | Usage |
|---|---|---|
| `products` | catalogue de verres saisi par l'expert | base produit du projet |
| `expert_annotations` | note + verification par question (`field`) | jeu de donnees pour affiner les regles plus tard |
| `recommendation_logs` | profil + reco generee (optionnel) | analyse a posteriori |

Les annotations sont **collectees uniquement** : elles n'influencent pas l'agent
en direct. Pour les exploiter, exporte la table `expert_annotations` depuis
Supabase ou ajoute une page de revue.
