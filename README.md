# s.rangedace.fr – Raccourcisseur d'URL

Fonctionnalités :
- Page d'accueil avec champ + bouton "Raccourcir l'URL".
- Génère un lien `s.rangedace.fr/XXXXXX`.
- Expiration : 30 jours sans utilisation (le compteur se remet à zéro à chaque clic).
- Codes expirés remis dans le pool pour réutilisation.

## Démarrage avec Docker Compose

```bash
# Place ce repo dans /opt/docker/shorten/app sur ta VM
cd /opt/docker/shorten/app
docker compose up -d --build
# http://localhost:8000 (ou via ton domaine)
```

Volumes/bind mounts (déjà dans `docker-compose.yml`) :
- Code : `/opt/docker/shorten/app` monté en RO dans le conteneur.
- Données Postgres : `/opt/docker/shorten/db` persiste la base.

Variables utiles :
- `BASE_URL` : URL publique utilisée dans les réponses (ex: `https://s.rangedace.fr`).
- `DATABASE_URL` : `postgresql://...` (par défaut `postgresql://shorten:shorten@db:5432/shorten`).
- `INACTIVITY_DAYS` : jours d'inactivité avant expiration (défaut 30).
- `CODE_LENGTH` : longueur du code (défaut 6).

## Sans Compose (dev rapide)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://shorten:shorten@localhost:5432/shorten"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Ouvre `http://localhost:8000`.
