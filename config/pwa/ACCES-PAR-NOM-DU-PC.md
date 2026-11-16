# Ouvrir BHH Access par le nom du PC (quand l'adresse IP change)

Le Wi-Fi donne au PC une adresse IP qui peut changer : un jour `192.168.1.25`, le lendemain
`192.168.1.40`. Une icône installée avec l'adresse IP cesse alors de marcher.

Le PC a aussi un **nom sur le Wi-Fi**, de la forme `nom-du-pc.local`. Ce nom ne change pas : le
téléphone retrouve le PC quelle que soit son adresse du moment. Le certificat créé par
`generer-certificat.ps1` contient ce nom : on peut donc installer l'application avec lui.

| | iPhone | Android |
|---|---|---|
| Nom `.local` reconnu | Oui, toujours | Selon le modèle et la version d'Android (souvent oui à partir d'Android 12) |
| Recommandation | Installer avec le nom du PC | Tester le nom ; s'il ne marche pas, garder l'adresse IP |

---

## 1. Connaître le nom du PC

Le nom est écrit dans **`config/pwa/certs/nom.txt`** (créé par `generer-certificat.ps1`),
par exemple `bureau-securite.local`.

Pour le retrouver autrement : sur le PC, **Paramètres ▸ Système ▸ Informations ▸ Nom de l'appareil**,
en minuscules, suivi de `.local`.

Vérification depuis le PC (PowerShell) :

```powershell
ping -4 nom-du-pc.local
```

Une réponse avec l'adresse actuelle du PC veut dire que le nom fonctionne sur ce réseau.

> Si le nom du PC est changé un jour, relancer `generer-certificat.ps1` : le certificat doit
> contenir le nouveau nom.

## 2. Prérequis

- Le **certificat de l'autorité** est déjà installé sur le téléphone
  ([INSTALLATION-IPHONE.md](INSTALLATION-IPHONE.md) ou [INSTALLATION-ANDROID.md](INSTALLATION-ANDROID.md),
  étapes 1 et 2). Rien de plus à installer pour utiliser le nom.
- Le téléphone et le PC sont sur **le même Wi-Fi**.
- L'application tourne sur le PC : `cd frontend ; npm run dev:phone`.

## 3. Sur iPhone

1. Supprimer l'ancienne icône si elle a été installée avec l'adresse IP
   (appui long ▸ **Supprimer l'app** ▸ **Supprimer de l'écran d'accueil**).
2. Dans **Safari**, ouvrir `https://nom-du-pc.local:5173`.
   La page s'ouvre **sans avertissement**.
3. **Partager** ▸ **Sur l'écran d'accueil** ▸ **Ajouter**.

L'icône continue de fonctionner quand l'adresse IP du PC change.

## 4. Sur Android

1. Dans **Chrome**, essayer `https://nom-du-pc.local:5173`.
   - **La page s'ouvre** : supprimer l'ancienne icône si besoin, puis menu **⋮** ▸
     **Installer l'application**. L'icône suivra le PC.
   - **« Ce site est inaccessible »** : ce téléphone ne reconnaît pas les noms `.local`.
     Utiliser l'adresse IP (`https://<adresse-du-PC>:5173`). Quand elle change, il faudra
     réinstaller l'icône avec la nouvelle adresse.
2. Sur certains téléphones, le **DNS privé** empêche les noms `.local` :
   Paramètres ▸ Réseau et Internet ▸ **DNS privé** ▸ **Automatique**, puis réessayer.

## 5. Appairer le téléphone avec le nom

Dans le back-office, Paramétrage ▸ Téléphones ▸ **Générer un code**. Le lien proposé reprend
l'adresse ouverte dans le navigateur du PC. Pour un lien qui suit le PC, ouvrir le back-office avec
`https://nom-du-pc.local:5173/admin` avant de générer le code. Sinon, saisir le code à la main sur
le téléphone.

---

## Problèmes fréquents

| Ce que je vois | Ce qu'il faut faire |
|---|---|
| « Cette connexion n'est pas privée » avec le nom | Le certificat a été créé avant l'ajout du nom, ou le PC a été renommé : relancer `generer-certificat.ps1` puis `npm run dev:phone`. |
| Le nom ne répond pas, même depuis le PC (`ping`) | Le réseau bloque ces noms (fréquent sur les Wi-Fi d'entreprise ou d'invités) : utiliser l'adresse IP. |
| Marche sur iPhone, pas sur Android | Normal sur certains Android : utiliser l'adresse IP sur ce téléphone. |
| Le nom marchait, plus maintenant | Vérifier que le PC est allumé, sur le même Wi-Fi, et que `npm run dev:phone` tourne. Autoriser Node.js dans le pare-feu Windows (réseaux privés). |

> Pour la production, la bonne solution est un nom fixe sur le serveur de l'entreprise
> (ex. `acces.bhh.local`, voir `nginx-production.conf.example`) : plus de dépendance à un PC.
