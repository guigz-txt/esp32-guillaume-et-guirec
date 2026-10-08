# COGIP - Pointage ESP32 + FastAPI

Projet autonome pour gérer le pointage des employés.

## Fonctionnalités

- Serveur FastAPI
- SQLite sans installation de PostgreSQL
- Swagger : `/docs`
- Page web : `/`
- API ESP32 : `POST /api/scan`
- Création d'employés
- Entrée / sortie automatique
- Historique des pointages
- Statut des employés
- Interface utilisable depuis un autre appareil du réseau local

## Installation Windows

Ouvre PowerShell dans ce dossier :

```powershell
cd C:\chemin\vers\COGIP
py -m pip install -r requirements.txt
py run_server.py
```

Ou double-clique sur `start_server.bat`.

## Adresse

Le serveur écoute sur toutes les interfaces réseau (`0.0.0.0`).

Exemple :

- PC : `http://192.168.1.160:8000/`
- Swagger : `http://192.168.1.160:8000/docs`
- ESP32 : `http://192.168.1.160:8000/api/scan`

L'adresse IP affichée au démarrage dépend de ton réseau.

## API ESP32

Envoyer un badge :

```http
POST /api/scan
Content-Type: application/json

{
  "badge_id": "ABC123",
  "device_id": "ESP32-01"
}
```

Réponse :

```json
{
  "success": true,
  "message": "Entrée enregistrée",
  "employee": {
    "id": 1,
    "badge_id": "ABC123",
    "name": "Jean Dupont"
  },
  "action": "IN"
}
```

Un scan alterne automatiquement entre ENTRÉE et SORTIE.

## Premier test

La base est créée automatiquement.

Depuis la page web, ajoute un employé avec un badge, par exemple :

- Nom : Jean Dupont
- Badge : ABC123

Puis utilise Swagger ou PowerShell :

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/scan" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"badge_id":"ABC123","device_id":"TEST"}'
```

## Pare-feu Windows

Si les autres appareils du réseau ne peuvent pas ouvrir le site, Windows peut bloquer le port 8000.

Dans PowerShell administrateur :

```powershell
New-NetFirewallRule -DisplayName "COGIP FastAPI 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

## Structure

```text
COGIP/
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── static/
│       └── index.html
├── run_server.py
├── requirements.txt
├── start_server.bat
├── README.md
└── cogip.db              # créé automatiquement au premier lancement
```
