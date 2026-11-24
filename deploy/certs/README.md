# Certificat HTTPS du serveur

Déposer ici, sur le serveur uniquement (jamais dans Git) :

- `server.crt` : certificat du serveur suivi des certificats intermédiaires (chaîne complète) ;
- `server.key` : sa clé privée (droits 600).

Le nom du certificat doit correspondre à `BHH_SERVER_NAME` (fichier `.env`), et l'autorité qui l'a signé doit être installée sur les téléphones : sans HTTPS reconnu, le navigateur refuse la caméra. Voir `config/pwa/README.md`.

Après un renouvellement : `docker compose restart web`.
