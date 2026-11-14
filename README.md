# TousMesLikes

Application web locale pour agréger, explorer et rechercher intelligemment tous les contenus likés, commentés, sauvegardés ou postés sur tes réseaux sociaux et plateformes préférés — le tout sur ta machine, sans service cloud.

## 🎯 Pourquoi ce projet

Tu as déjà voulu retrouver un post, une vidéo ou un article que tu avais aimé il y a quelques mois, mais tu ne sais plus sur quel réseau ni comment le chercher ? L'idée est simple : importer tes exports de données (Twitter/X, Facebook, LinkedIn, Reddit, Instagram, YouTube, ChatGPT, Claude) dans une seule app qui :

- **Regroupe** tous tes contenus en un seul endroit
- **Enrichit** automatiquement les posts (texte complet + images) via des APIs officielles ou scrapers payants
- **Catégorise** intelligemment via un LLM local (Mistral) et analyse les images via un modèle vision (LLaVA)
- **Recherche** en plein texte (FTS) ou en sémantique (embeddings + RAG)
- **Visualise** tes centres d'intérêt sous forme de collections thématiques et de graphes

Tout tourne **en local** : par défaut, tes données ne quittent jamais ta machine.

## 🧩 Stack technique

| Composant | Techno |
|---|---|
| Backend | Python 3.13, FastAPI, SQLite (+ FTS5) |
| Recherche vectorielle | ChromaDB |
| LLM local | Ollama (Mistral, nomic-embed-text, LLaVA) |
| Frontend | React 18, Vite, Tailwind CSS, D3.js, Recharts |
| Enrichissement | X API officielle (tweets), API publique Reddit, Apify (Facebook, Instagram, LinkedIn) |
| Médias | ffmpeg pour le merge audio/vidéo Reddit |

## 🚀 Installation

### Prérequis

- **Python 3.13+**
- **Node.js 18+**
- **Ollama** installé et tournant ([ollama.com](https://ollama.com))
- **ffmpeg** (pour le son des vidéos Reddit) : `brew install ffmpeg`

### Étapes

1. Clone le repo et installe les dépendances :

```bash
# Backend
cd backend
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

2. Pull les modèles Ollama :

```bash
ollama pull mistral              # Chat + catégorisation (~4.4 GB)
ollama pull nomic-embed-text     # Embeddings pour recherche sémantique (~274 MB)
ollama pull llava                # Analyse d'images (~4.7 GB, optionnel)
```

3. Configure les clés API (voir section ci-dessous)

4. Lance l'app :

```bash
# Terminal 1 — Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Ouvre **http://localhost:5173**.

## 🔑 Variables d'environnement

Crée un fichier `backend/.env` :

```bash
# X/Twitter API (pour enrichir les likes/bookmarks avec le texte complet + médias)
# Obtenir : https://developer.x.com (plan Pay-per-use, ~$0.005/tweet)
X_BEARER_TOKEN=your_twitter_bearer_token

# Apify (pour enrichir Facebook, Instagram, LinkedIn)
# Obtenir : https://apify.com (coût variable selon la plateforme)
APIFY_API_KEY=your_apify_api_key
```

Les deux sont **optionnelles** — l'app fonctionne sans, mais les posts ne seront enrichis que par Reddit (API publique gratuite).

Pour stocker les médias ailleurs (NAS, disque externe), ajoute aussi :

```bash
# Dossier des médias (par défaut : backend/data/media)
MEDIA_PATH=/Volumes/MonPartage/TousMesLikes-media
```

La base SQLite et ChromaDB restent dans `backend/data/` : SQLite ne fonctionne pas de façon fiable sur un partage réseau. Si le dossier n'est pas disponible, l'app démarre quand même, sans afficher les médias. S'il est synchronisé avec un service cloud, les médias sont aussi copiés chez ce service.

## 📥 Importer tes données

Dans l'onglet **Importer** :

1. Récupère tes exports de données (guides en jeu dans l'UI)
2. Upload le fichier correspondant au type sélectionné

**Fichiers supportés** :

| Plateforme | Fichier |
|---|---|
| X / Twitter | `like.js`, `tweet.js`, `bookmark.js` (export tiers) |
| Facebook | `likes_and_reactions.json`, `pages_you've_liked.json`, `comments.json`, `group_posts_and_comments.json`, `your_comments_in_groups.json`, `posts_on_other_pages_and_profiles.json`, etc. |
| LinkedIn | `Reactions.csv`, `Comments.csv`, `Shares.csv`, `SavedItems.csv` (export **Complete**, pas Basic) |
| Reddit | Export CSV ou JSON |
| Instagram | `liked_posts.json` |
| YouTube | `watch-history.json`, `likes.json`, `my-comments.html` |
| ChatGPT | `conversations.json` |
| Claude | JSON export |

Les doublons sont automatiquement ignorés (dédoublication par `platform` + `raw_json`).

## 🧠 Fonctionnalités clés

### Dashboard
Vue d'ensemble : nombre d'items, répartition par plateforme, timeline, collections thématiques auto-générées (style Google Photos Memories), treemap des catégories.

### Explorer
Liste complète avec filtres combinables :
- Par plateforme (boutons colorés)
- Par année / mois (navigation hiérarchique)
- Par thématique
- Tri par date (récent / ancien / dernier import)
- Infinite scroll

### Recherche
- **Texte** (FTS SQLite) — rapide, exacte, idéale pour mots-clés précis
- **IA / Sémantique** (embeddings Ollama) — pour requêtes conceptuelles ("projet sur le tricot", "article sur l'urbanisme")

### Chat IA
Interface RAG : pose une question, Mistral répond en citant les posts les plus pertinents de ta base.

### Visualisation
Graphe force-directed (D3) montrant les relations entre thématiques basé sur les co-occurrences.

## ⚙️ Pipeline d'enrichissement

Les exports contiennent souvent des URLs sans le contenu. L'app enrichit les items via :

| Plateforme | Méthode | Coût |
|---|---|---|
| Reddit | API publique `.json` | Gratuit |
| Twitter | X API v2 | ~$0.005/tweet |
| Facebook | Apify | ~$0.001/post |
| Instagram | Apify | ~$0.002/post |
| LinkedIn | Apify (`supreme_coder/linkedin-post`) | ~$0.001/post |

L'enrichissement télécharge aussi les images et vidéos (pas les vidéos Twitter/Facebook pour éviter de saturer le disque).

Pour Reddit, un script ffmpeg merge automatiquement les pistes vidéo + audio (Reddit les stocke séparément).

## 🗂️ Arborescence

```
Tousmeslikes/
├── backend/
│   ├── app/
│   │   ├── main.py              # Endpoints FastAPI
│   │   ├── database.py          # SQLite + FTS5 + WAL
│   │   ├── parsers/             # Un parser par plateforme
│   │   ├── enricher.py          # Appels X API, Apify, Reddit
│   │   ├── categorizer.py       # Catégorisation par taxonomie (keyword)
│   │   ├── smart_categorizer.py # Catégorisation LLM (Mistral + LLaVA)
│   │   ├── vector_store.py      # ChromaDB + embeddings Ollama
│   │   └── ollama_client.py     # Détection d'Ollama
│   ├── data/                    # SQLite DB + médias + ChromaDB (GITIGNORED)
│   ├── requirements.txt
│   └── .env                     # Clés API (GITIGNORED)
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ItemList.jsx     # Cards avec médias + lightbox
│   │   │   ├── SearchBar.jsx    # Texte vs IA
│   │   │   ├── ChatPanel.jsx    # RAG
│   │   │   ├── Collections.jsx  # Collections thématiques
│   │   │   ├── TopicGraph.jsx   # Graphe D3
│   │   │   └── Upload.jsx
│   │   └── api.js
│   └── package.json
└── README.md
```

## ⚠️ Points d'attention

- **La base de données `backend/data/tousmeslikes.db` peut devenir grosse** (plusieurs Go avec les médias). Le dossier `data/` est **gitignoré**.
- **Ollama doit tourner** pour que la recherche sémantique, le chat et la catégorisation LLM fonctionnent. Sinon, l'app bascule sur le keyword matching et la recherche FTS.
- **Les clés API sont sensibles** : ne commits JAMAIS ton `.env`. Le `.gitignore` racine l'exclut déjà.
- **Rate limits** :
  - Reddit : 429 très fréquents, l'enrichisseur attend et retry
  - X API : limite mensuelle selon ton plan
  - Apify : payant à l'usage
- **Posts supprimés/privés** : certains items ne peuvent plus être enrichis (post supprimé, compte privé, etc.) — ils restent dans la base avec le contenu minimal de l'export.
- **Première indexation longue** : sur ~30k items, comptez plusieurs heures au total (enrichissement + embeddings + catégorisation LLM + analyse d'images).

## 🔐 Sécurité & confidentialité

- Tout tourne en local — aucun service cloud sauf les APIs d'enrichissement (Apify, X API) qui reçoivent uniquement les URLs publiques, pas tes données.
- Aucune télémétrie.
- Ton fichier `.env` et ta base de données ne quittent jamais ta machine. Les médias suivent le dossier choisi via `MEDIA_PATH`.

## 📜 Licence

Projet personnel. Réutilise librement pour ton usage.
