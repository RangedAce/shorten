# s.rangedace.fr – Raccourcisseur d'URL

Fonctionnalités :
- Page d'accueil avec champ + bouton "Raccourcir l'URL".
- Génère un lien `s.rangedace.fr/XXXXXX`.
- Expiration : 30 jours sans utilisation (le compteur se remet à zéro à chaque clic).
- Codes expirés remis dans le pool pour réutilisation.

## Démarrage avec Docker Compose

```bash
docker compose up -d --build
# Ouvre http://localhost:8000
```

Variables utiles (déjà posées dans `docker-compose.yml`) :
- `BASE_URL` : URL publique utilisée dans les réponses (ex: `https://s.rangedace.fr`).
- `DATABASE_URL` : `postgresql://...` (par défaut `postgresql://shorten:shorten@db:5432/shorten`).
- `INACTIVITY_DAYS` : jours d'inactivité avant expiration (défaut 30).
- `CODE_LENGTH` : longueur du code (défaut 6).

Le volume `pgdata` (défini dans Compose) persiste la base Postgres.

## Sans Compose (dev rapide)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://shorten:shorten@localhost:5432/shorten"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Ouvre `http://localhost:8000`.
