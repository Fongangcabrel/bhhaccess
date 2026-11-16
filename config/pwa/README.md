# BHH Access sur les téléphones (PWA)

L'application des agents est une **PWA** : elle s'ouvre dans le navigateur du téléphone puis
s'installe sur l'écran d'accueil, avec le logo, en plein écran. Rien à télécharger sur un store.

La caméra et l'installation exigent du **HTTPS avec un certificat que le téléphone reconnaît**.
Avec un certificat non reconnu, on obtient une icône « B » au lieu du logo, et l'application
installée refuse de s'ouvrir. Ce dossier règle ce point pour les essais.

| Fichier | Rôle |
|---|---|
| `generer-certificat.ps1` | Crée le certificat HTTPS du PC (à relancer si l'adresse IP du PC change). |
| `INSTALLATION-IPHONE.md` | Pas à pas pour un iPhone (Safari). |
| `INSTALLATION-ANDROID.md` | Pas à pas pour un Android (Chrome). |
| `ACCES-PAR-NOM-DU-PC.md` | Ouvrir l'application par le nom du PC (`nom-du-pc.local`) : l'icône marche même quand l'IP change. |
| `nginx-production.conf.example` | Modèle pour la production (serveur interne, certificat de l'entreprise). |
| `certs/` | Créé par le script. **Jamais dans Git** : contient la clé privée du serveur. |

## Essais sur téléphone : côté PC (une fois)

1. Installer l'outil, une seule fois :
   ```powershell
   winget install --id FiloSottile.mkcert -e
   ```
2. Créer les certificats, depuis la racine du projet :
   ```powershell
   powershell -ExecutionPolicy Bypass -File config\pwa\generer-certificat.ps1
   ```
   Windows peut demander d'accepter le certificat « mkcert » : répondre **Oui**.
   Le script détecte l'adresse Wi-Fi du PC (sinon : `-Ip 192.168.1.25`) et l'écrit dans `certs/adresse.txt`.
3. Lancer l'API, puis l'application ouverte au réseau Wi-Fi :
   ```powershell
   cd backend ; .venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload --port 8001
   cd frontend ; npm run dev:phone
   ```
   Vite utilise automatiquement `certs/dev-cert.pem` quand il existe.
4. Si les téléphones n'arrivent pas à joindre le PC : autoriser Node.js dans le **pare-feu Windows**,
   sur les réseaux **privés**. Windows le propose au premier lancement ; sinon, Paramètres ▸ Confidentialité
   et sécurité ▸ Sécurité Windows ▸ Pare-feu ▸ Autoriser une application.

## Essais sur téléphone : côté téléphone (une fois par téléphone)

Le certificat à installer est servi par l'application elle-même :
`https://<adresse-du-PC>:5173/bhh-dev-ca.crt`

- iPhone ➜ [INSTALLATION-IPHONE.md](INSTALLATION-IPHONE.md)
- Android ➜ [INSTALLATION-ANDROID.md](INSTALLATION-ANDROID.md)

Ensuite, on appaire le téléphone comme d'habitude : back-office ▸ Paramétrage ▸ Téléphones ▸
« Générer un code », puis le code ou le lien `https://<adresse-du-PC>:5173/pair/<code>` sur le téléphone.

## Si l'adresse IP du PC change

Le Wi-Fi peut donner une autre adresse au PC. Relancer `generer-certificat.ps1`, puis redémarrer
`npm run dev:phone`. Les téléphones **n'ont rien à refaire** : leur certificat reste valable.
Ils devront simplement ouvrir la nouvelle adresse et réinstaller l'icône.
Pour éviter cela, on peut fixer l'adresse du PC dans la box ou le routeur (réservation DHCP).

Autre solution, sans rien fixer : le certificat contient aussi le **nom du PC sur le Wi-Fi**
(écrit dans `certs/nom.txt`, de la forme `nom-du-pc.local`). Ouvrir et installer l'application avec
`https://nom-du-pc.local:5173` : l'icône continue de marcher quand l'adresse IP change.
Fiable sur iPhone. Sur Android, cela dépend du modèle : sinon, utiliser l'adresse IP.
Pas à pas : [ACCES-PAR-NOM-DU-PC.md](ACCES-PAR-NOM-DU-PC.md).

Au démarrage, `npm run dev:phone` prévient si l'adresse du PC ne correspond plus au certificat.

## Sécurité

- `certs/dev-key.pem` et le dossier de mkcert (`mkcert -CAROOT`, en particulier `rootCA-key.pem`)
  ne doivent jamais être partagés : ils permettent de fabriquer des certificats acceptés par les
  téléphones qui ont installé l'autorité.
- Après les essais, on peut retirer l'autorité des téléphones :
  - iPhone : Réglages ▸ Général ▸ VPN et gestion de l'appareil ▸ profil mkcert ▸ Supprimer.
  - Android : Chiffrement et identifiants ▸ Identifiants de confiance ▸ Utilisateur ▸ mkcert ▸ Supprimer.
- Sur le PC : `mkcert -uninstall`.

## En production

L'application compilée (`npm run build`, dossier `frontend/dist`) et l'API sont servies par un
serveur interne en HTTPS, avec un **certificat émis par l'entreprise** (autorité interne déployée sur
les téléphones, idéalement par l'outil de gestion des appareils). Partir de
`nginx-production.conf.example`. Une fois ce certificat en place, les téléphones installent
l'application directement (étape 3 des guides) : plus besoin de mkcert.
