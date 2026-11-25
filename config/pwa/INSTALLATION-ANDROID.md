# Installer BHH Access sur un téléphone Android

Environ 3 minutes, **une seule fois par téléphone**. Il faut l'adresse du PC qui fait tourner
l'application (ex. `192.168.1.25`) : elle est écrite dans `config/pwa/certs/adresse.txt`.

Le téléphone et le PC doivent être sur **le même Wi-Fi**. Utiliser **Google Chrome**.

---

## 1. Télécharger le certificat

1. Ouvrir **Chrome** et taper : `https://192.168.1.25:5173/bhh-dev-ca.crt`
   (remplacer par l'adresse du PC).
   - Si Chrome affiche « Votre connexion n'est pas privée » : **Paramètres avancés** ▸
     **Continuer vers le site**. C'est normal, le certificat n'est pas encore installé.
2. Le fichier **bhh-dev-ca.crt** est téléchargé.
   - Si Android propose directement de le nommer et de l'installer : choisir
     **Utilisation : VPN et applications** ou **Certificat CA**, puis passer à l'étape 3.

## 2. Installer le certificat comme « certificat CA »

Le chemin change selon la marque. Le plus simple : ouvrir **Paramètres** et chercher **« certificat »**.

- **Android standard (Pixel, Nokia, Motorola…)** :
  Paramètres ▸ Sécurité et confidentialité ▸ Plus de paramètres de sécurité ▸
  **Chiffrement et identifiants** ▸ **Installer un certificat** ▸ **Certificat CA**.
- **Samsung** :
  Paramètres ▸ Sécurité et confidentialité ▸ Autres paramètres de sécurité ▸
  **Installer depuis le stockage** ▸ **Certificat CA**.
- **Xiaomi / Redmi** :
  Paramètres ▸ Mots de passe et sécurité ▸ Confidentialité ▸ **Chiffrement et identifiants** ▸
  **Installer un certificat** ▸ **Certificat CA**.
- **Tecno / Infinix / Itel** :
  Paramètres ▸ Sécurité ▸ **Chiffrement et identifiants** ▸ **Installer un certificat** ▸ **Certificat CA**.

Puis :

1. Android avertit : « Vos données ne seront pas privées… » ➜ **Installer quand même**.
   C'est le message normal pour tout certificat ajouté à la main.
2. Choisir le fichier **bhh-dev-ca.crt** dans **Téléchargements**.
3. Si le téléphone n'a pas de verrouillage d'écran, Android demande d'en créer un (code ou schéma) :
   c'est obligatoire pour installer un certificat.

Vérification : **Chiffrement et identifiants ▸ Identifiants de confiance ▸ Utilisateur** ➜ « mkcert … » apparaît.

## 3. Installer l'application

1. Fermer Chrome complètement (glisser l'appli vers le haut dans les applis récentes), puis le rouvrir.
2. Ouvrir `https://192.168.1.25:5173` : la page s'ouvre **sans avertissement** (cadenas normal).
3. Menu **⋮** ▸ **Installer l'application** (ou **Ajouter à l'écran d'accueil** ▸ **Installer**).
4. L'icône **BHH Access** avec le logo apparaît. Elle s'ouvre en plein écran, comme une application.

Au premier scan, autoriser l'accès à la **caméra**.

---

## Problèmes fréquents

| Ce que je vois | Ce qu'il faut faire |
|---|---|
| Pas de « Installer l'application » dans le menu | Le certificat n'est pas reconnu : vérifier l'étape 2, fermer et rouvrir Chrome. |
| « Votre connexion n'est pas privée » sur l'application | Certificat pas installé en « Certificat CA », ou adresse IP du PC changée : demander qu'on relance `generer-certificat.ps1`. |
| La page ne charge pas du tout | Vérifier le Wi-Fi (même réseau que le PC) et que l'application tourne sur le PC (`npm run dev:phone`). |
| Le scan ne marche plus, aucune donnée (postes, historique) alors que tout marchait | L'adresse IP du PC a sans doute changé (comparer avec `certs/adresse.txt`) : relancer `generer-certificat.ps1` puis redémarrer `npm run dev:phone`. |
| Écran de la caméra noir | Toucher le bouton « Touchez ici pour activer la caméra » s'il s'affiche. Sinon : fermer l'application, la rouvrir, et vérifier que Chrome a accès à la caméra (Paramètres des sites ▸ Caméra). |
| Icône sans logo / ancienne icône | Désinstaller l'icône (appui long ▸ Désinstaller), Chrome ▸ Paramètres ▸ Paramètres des sites ▸ Toutes les données des sites : supprimer l'adresse du PC, puis refaire l'étape 3. |
| Pas de voix | Paramètres ▸ Accessibilité ▸ Synthèse vocale : moteur Google, langue Français ; télécharger la voix si besoin. |

> Ce certificat sert aux **essais**. En production, l'application est servie par le serveur de
> l'entreprise avec son propre certificat (voir `nginx-production.conf.example`).
