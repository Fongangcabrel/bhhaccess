# Installer BHH Access sur un iPhone

Environ 3 minutes, **une seule fois par iPhone**. Il faut l'adresse du PC qui fait tourner
l'application (ex. `192.168.1.25`) : elle est écrite dans `config/pwa/certs/adresse.txt`.

L'iPhone et le PC doivent être sur **le même Wi-Fi**.

---

## 1. Installer le certificat (pour que l'iPhone fasse confiance au PC)

1. Ouvrir **Safari**. Pas Chrome : sur iPhone, seul Safari sait installer un certificat.
2. Taper l'adresse : `https://<adresse-du-PC>:5173/bhh-dev-ca.crt`
   (remplacer par l'adresse du PC).
   - Si Safari affiche « Cette connexion n'est pas privée » : toucher **Afficher les détails**,
     puis **visiter ce site web** et confirmer. C'est normal, le certificat n'est pas encore installé.
3. Safari demande : « Ce site web tente de télécharger un profil de configuration » ➜ **Autoriser**.
   Le message « Profil téléchargé » s'affiche ➜ **Fermer**.
4. Ouvrir **Réglages**. En haut, toucher **Profil téléchargé**.
   Si la ligne n'y est pas : **Réglages ▸ Général ▸ VPN et gestion de l'appareil**, puis le profil
   « mkcert … ».
5. Toucher **Installer** (en haut à droite), saisir le code de l'iPhone, puis **Installer** encore deux fois.

## 2. Activer la confiance

Sans cette étape, l'iPhone garde le certificat mais ne lui fait pas encore confiance.

1. **Réglages ▸ Général ▸ Informations**.
2. Tout en bas : **Réglages des certificats** (ou « Réglages de confiance des certificats »).
3. Activer l'interrupteur à côté de **mkcert …**, puis **Continuer**.

## 3. Installer l'application sur l'écran d'accueil

1. Si un ancien raccourci « B » existe : appui long dessus ▸ **Supprimer l'app** ▸ **Supprimer de l'écran d'accueil**.
2. Dans **Safari**, ouvrir `https://<adresse-du-PC>:5173` : la page s'ouvre **sans avertissement**.
3. Toucher le bouton **Partager** (carré avec une flèche), puis **Sur l'écran d'accueil** ▸ **Ajouter**.
4. L'icône **BHH Access** avec le logo apparaît. Elle s'ouvre en plein écran, comme une application.

Au premier scan, autoriser l'accès à la **caméra**.

---

## Problèmes fréquents

| Ce que je vois                                            | Ce qu'il faut faire                                                                                                          |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Une icône « B » au lieu du logo                        | Le certificat n'est pas installé ou pas activé (étapes 1 et 2). Supprimer l'icône, puis refaire l'étape 3.              |
| « Cette connexion n'est pas privée » sur l'application | L'étape 2 (confiance) n'est pas faite, ou l'adresse IP du PC a changé : demander qu'on relance `generer-certificat.ps1`. |
| La page ne charge pas du tout                             | Vérifier le Wi-Fi (même réseau que le PC) et que l'application tourne sur le PC (`npm run dev:phone`).                  |
| L'application installée reste blanche                    | Réglages ▸ Safari ▸ Avancé ▸ Données de sites web : supprimer l'adresse du PC, puis refaire l'étape 3.                |
| Pas de son ni de voix                                     | Toucher une fois l'écran après l'ouverture (iOS bloque le son avant). Vérifier que le bouton silencieux est désactivé.  |
| La voix ne parle pas français                            | Réglages ▸ Accessibilité ▸ Contenu énoncé ▸ Voix ▸ Français : télécharger une voix.                               |

> Ce certificat sert aux **essais**. En production, l'application est servie par le serveur de
> l'entreprise avec son propre certificat (voir `nginx-production.conf.example`).
