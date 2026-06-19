# Prompt — Migration 100% piloté par la VM + ChromaDB catalogue RÉEL

## Contexte
- Front : app Streamlit `app.py` (+ `pages/1_Produits.py`), moteur local `agent.py` (`EssilorAgent`, règles déterministes OptiGuide), `db.py` (Supabase).
- Backend VM : FastAPI "Configurable Call Center LLM v3.0" exposé via devtunnel sur
  `https://zf04gvh1-8020.uks1.devtunnels.ms` (port 8020). GPU Tesla T4. Endpoints clés :
  `POST /chat/recommendation`, `POST /v1/chat/completions` (OpenAI-compat),
  `GET /v1/catalogue/search?q=...&top_k=...`, `GET /health`.
- Le scénario reco de la VM est déjà aligné sur OptiGuide (mêmes règles et noms de champs
  que `agent.py` : `computer_usage`, `sun_discomfort`, ADD>2.25→S Design, bump 1.56→1.60,
  lumière bleue→Prevencia, portable→Short).

## Objectif
Faire piloter le parcours de recommandation **à 100% par la VM** (la VM est la seule source
de vérité), enrichir la reco avec les **vrais produits du catalogue Essilor (ChromaDB)**, et
garder `EssilorAgent` local **uniquement comme fallback hors-ligne** si la VM est injoignable.

---

## PARTIE A — Backend VM : ChromaDB catalogue RÉEL

Problème actuel : `GET /v1/catalogue/search?q=Varilux` renvoie `count: 0` alors que
`/health` indique `essilor_catalogue.products_loaded: 23`, `collection_count: 29`,
`ready: true`. La recherche n'est pas correctement branchée sur la collection ChromaDB.

À faire côté VM :
1. **Réparer `/v1/catalogue/search`** pour qu'il interroge réellement la collection
   `essilor_catalogue` (embeddings `paraphrase-multilingual-MiniLM-L12-v2`). Vérifier le nom
   de collection, que les documents sont bien indexés, et que `q` est embeddé puis cherché.
   Retour attendu : `{query, count, results:[{code, nom, marque, geometrie, matiere, indice,
   photochromique, diametre, score}]}`.
2. **Enrichir `/chat/recommendation`** : quand le profil est complet et la reco construite,
   mapper la reco abstraite (`lens_type` + `index` + `treatment` + `transition` + `geometrie`)
   vers les **vraies références produits** via la collection ChromaDB (ou le RAG
   `rag_catalogue_verres`). Ajouter au JSON de réponse un champ :
   ```json
   "catalogue_matches": [
     {"code": "25FC52", "nom": "VX COMFORT 3.0 FIT TR GRAPHITE",
      "marque": "Varilux Comfort 3.0 Fit", "indice": "1.503",
      "matiere": "Orma", "photochromique": "TRANSITIONS GRAPHITE",
      "diametre": "70/75", "score": 0.41}
   ]
   ```
   Filtrer/scorer par cohérence avec `lens_type` (marque/gamme), `index` (indice matière) et
   `transition` (photochromique). Renvoyer le top 3-5.
3. Ne PAS inventer de produit : si aucun match ChromaDB, renvoyer `catalogue_matches: []` et
   conserver la reco abstraite.
4. (Optionnel) Exposer le prix réel via le tool `get_price` pour chaque match.

Critères d'acceptation A :
- `GET /v1/catalogue/search?q=Varilux&top_k=3` renvoie `count>0` avec de vrais codes.
- `POST /chat/recommendation` (profil complet) renvoie `recommendation` + `catalogue_matches`
  non vide avec des codes/références réels cohérents.

---

## PARTIE B — Front : brancher app.py sur la VM (100% VM) + fallback local

À faire dans ce repo :
1. Utiliser `vm_client.py` (déjà présent : `VMRecommendationClient.recommend(session_id,
   message, profile, reset)` → `/chat/recommendation`).
2. Dans `app.py`, remplacer l'usage direct de `EssilorAgent` pour le parcours par des appels
   à la VM :
   - garder un `session_id` stable par session Streamlit (`st.session_state`).
   - à chaque message utilisateur → `client.recommend(session_id, message=...)`.
   - afficher `response` (texte), la progression via `missing_fields`/`next_questions`, et
     quand `recommendation` ≠ null → afficher la reco **et** `catalogue_matches` (produits
     réels : code, nom, marque, indice, matière, Ø).
3. **Fallback** : envelopper l'appel VM dans un try/except (timeout/connexion). En cas d'échec,
   basculer sur `EssilorAgent` local (déjà fonctionnel offline) et afficher un bandeau
   "Mode hors-ligne (VM injoignable)". Garder le `session_id` pour reprendre quand la VM revient.
4. Config via `.env` (déjà fait) : `LLM_BASE_URL=.../v1`, `LLM_MODEL=essilor-recommendation-v1`,
   `LLM_API_KEY=optiguide`. Ajouter `VM_BASE_URL=https://zf04gvh1-8020.uks1.devtunnels.ms`.
   ⚠️ Écrire le `.env` **sans BOM** (un BOM fait lire la 1re clé comme vide).
5. Ne plus dupliquer les règles métier dans `agent.py` à l'avenir : la VM est la source de
   vérité ; `agent.py` ne sert plus que de secours.

Critères d'acceptation B :
- L'UI Streamlit conduit un parcours complet en parlant à la VM (questions une à une).
- La reco finale affiche les **produits réels** du catalogue.
- Couper la VM (ou le tunnel) → l'UI bascule en mode local sans crash, puis reprend la VM.

---

## Contrats API (référence)
- `POST /chat/recommendation` body : `{ "session_id": str, "message"?: str,
  "profile"?: object, "reset"?: bool, "top_k"?: int }`
  → `{ response, profile, extracted_updates, missing_fields, next_questions,
       next_question_fields, recommendation, catalogue_matches?, rag_results }`
- `GET /v1/catalogue/search?q=...&top_k=...` → `{ query, count, results[] }`
- `GET /health` → état runtime/RAG/catalogue/DB.
- Header tunnel pour requêtes non-navigateur si besoin : `X-Tunnel-Skip-AntiPhishing-Page: true`.
