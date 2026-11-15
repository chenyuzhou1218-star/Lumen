# Guide des fonctions de Lumen

Lumen est une équipe d'IA installée sur votre PC Windows. Vous ne parlez qu'à Lumen, en langage courant ; il confie chaque tâche au membre de l'équipe le mieux adapté, choisit lui-même les bons outils et vous remet le résultat une fois le travail terminé. Il sait écrire du code, rechercher des problèmes, monter des vidéos, créer de la 3D, réaliser des pages web et des PDF, faire des recherches sur internet et utiliser l'ordinateur.

## 1. Premiers pas

- **Ce qu'il faut** : Windows, Python 3.12, et une IA : Claude Code ou Codex (à connecter une fois dans le terminal après installation), ou une clé API (les services compatibles avec les interfaces OpenAI ou Anthropic conviennent).
- **Installation** : dans le dossier de Lumen, lancez `setup.ps1` (la version en chinois se trouve dans `安装环境.ps1`). Il crée un dossier `.venv` à cet endroit et y installe les paquets dont Lumen a besoin, sans toucher au Python de votre système. Ensuite, double-cliquez sur `Lumen.cmd` pour l'ouvrir.
- **Premier lancement** : après l'écran d'accueil, choisissez la langue de l'interface et un dossier de travail, et vous pouvez commencer. Le modèle peut être changé plus tard, sous la zone de saisie.
- **Lancements suivants** : Lumen retrouve le dernier dossier utilisé. La colonne de gauche permet de changer de dossier, d'ouvrir une nouvelle conversation et de rechercher dans les conversations.

## 2. Envoyer un message

- Écrivez ce que vous voulez faire dans la zone de saisie, puis appuyez sur Entrée pour envoyer. Vous pouvez glisser-déposer ou coller des fichiers.
- **Saisie vocale** : cliquez sur le microphone et parlez. Vous pouvez vous exprimer librement, Lumen comprend le sens et ne vous reprend pas sur la grammaire.
- **Modèle** : sous la zone de saisie, choisissez l'IA à utiliser (Claude Code, Codex ou un modèle du service que vous avez connecté), à côté du niveau de réflexion. Vous décidez seul du modèle, Lumen ne le change jamais de lui-même.
- **Quand il hésite, il vous demande d'abord** : si Lumen n'est pas sûr de bien comprendre votre demande, un panneau de questions s'affiche. Chaque question propose des choix ; il vous suffit de cliquer. Vous pouvez aussi passer la question et laisser Lumen décider.
- **Sous la réponse** : copier, mémoriser, répondre à nouveau, ou reformuler puis reposer la question. Une fois la réponse terminée, ses étapes se replient et seul le résultat reste visible ; dépliez-les pour voir chaque étape.

## 3. Mode d'approbation

Sous la zone de saisie, choisissez le mode d'approbation de cette conversation. Il détermine si l'IA doit vous demander la permission avant d'agir :

| Mode d'approbation | Quand il vous demande |
|---|---|
| Entièrement ouvert | Ne demande jamais, agit directement |
| Vérifier à ma place | Demande seulement avant de supprimer des fichiers et avant d'utiliser la souris ou le clavier sur l'ordinateur |
| Tout me demander | Demande avant chaque action qui modifie quelque chose |

Lorsqu'il faut une autorisation, une petite carte apparaît au-dessus de la zone de saisie, en bas à droite : une ligne décrit l'action, avec les boutons **Autoriser** et **Refuser** à côté. Refuser ne bloque que cette action ; les autres continuent normalement. En dehors de cela, Lumen n'a aucune autre restriction d'accès : tous les dossiers et tous les disques de l'ordinateur lui sont accessibles.

## 4. L'équipe Lumen

| Membre | Rôle |
|---|---|
| Lumen | Chef d'orchestre : vous parle, répartit le travail et vous donne la réponse finale |
| Spark | Écrit du code et utilise les différents outils de création |
| Prism | Inspecte le travail |
| Torch | Teste en conditions réelles : fait tourner le programme pour de bon |
| Ray | Recherche des informations sur internet |
| Lantern | Gère les fichiers |
| Beacon | Supervise : revérifie le résultat des autres |
| Iris | Utilise l'ordinateur |

Chaque membre a sa propre mémoire de travail et peut aussi faire appel à un assistant ponctuel. Les membres travaillent en même temps sans se gêner.

**Lumen est votre égal.** Il s'exprime comme un collègue compétent : si vous vous trompez, il vous le fait remarquer et explique pourquoi ; s'il a raison, il ne changera pas d'avis parce que vous insistez, sauf si vous lui donnez une bonne raison. Sur les décisions qui vous reviennent, c'est vous qui tranchez, et il s'y tient.

## 5. Utiliser les outils automatiquement (sans @)

Dites simplement ce que vous voulez faire, par exemple « transforme cette image en PDF », « coupe cette vidéo pour garder les 10 premières secondes », « fais un cube 3D rouge ». Lumen connaît les outils installés sur cet ordinateur, choisit celui qui convient et confie le travail au membre qui sait s'en servir.

Vous pouvez aussi taper @ dans la zone de saisie pour désigner un outil précis ; dans ce cas, seul l'outil désigné sera utilisé.

| Outil | Sert à |
|---|---|
| CodeCut | Monter des vidéos : couper, assembler, sous-titres, musique de fond, export |
| Code3D | Modèles et scènes 3D, avec le Blender installé sur votre ordinateur ; export en GLB et en images |
| CodeSound | Musique et effets sonores |
| CodePage | Pages web |
| CodeGame | Petits jeux jouables |
| CodeDeck | Diaporamas et documents (PowerPoint, Word, PDF) |
| CodeData | Analyser des fichiers Excel et CSV ; chaque chiffre du rapport est traçable jusqu'à sa source |
| CodeCAD | Pièces imprimables en 3D, cotes en millimètres |
| CodeLab | Suivre les journaux et la progression de l'entraînement des modèles |
| CodeTools | Des dizaines de petits outils : affiches de logo, organigrammes, codes QR, sous-titres, doublage, retouche d'images par lot, rangement de fichiers, etc. |
| CodeFilm | Un court métrage à partir d'une seule phrase |
| CodePDF | Convertir des images en PDF, fusionner, séparer, compresser, faire pivoter, extraire des pages |

## 6. Panneau de droite

- **Fenêtre d'outil** : quand l'équipe utilise un outil, la fenêtre s'ouvre automatiquement à droite et vous pouvez suivre le travail. Cette fenêtre est réservée à l'IA : elle clique et écrit dedans sans prendre votre souris ni votre clavier, et vous voyez un petit pointeur bleu se déplacer. Cliquez sur × en haut de la fenêtre pour la fermer.
- **Navigateur** (Ctrl+Shift+B) : recherchez et ouvrez des pages web ici ; les adresses cliquées dans le chat s'ouvrent aussi ici. Quand l'équipe fait des recherches sur internet, cela s'affiche également ici.
- **Terminal** (Ctrl+J) : un vrai PowerShell, ouvert dans le dossier en cours. Les commandes lancées par l'équipe s'affichent ici en couleur.

## 7. Mémoire à long terme

- **L'IA se souvient de vous** : avant chaque nouvelle conversation, l'IA relit les conversations précédentes et en résume l'essentiel dans une mémoire : ce qui concerne **vous** (qui vous êtes, votre manière de vous exprimer, vos goûts, les règles que vous avez fixées, valables pour tous les projets) et ce qui concerne **ce projet** (ce qui a été fait, ce qui a été décidé, où en est le travail). La nouvelle conversation démarre avec cette mémoire, vous n'avez donc pas à tout réexpliquer à chaque fois.
- **La taille suit l'historique** : si vous avez peu discuté, elle tient en quelques lignes ; si vous avez beaucoup discuté, elle s'allonge, en général jusqu'à 50 000 caractères, et 80 000 environ au maximum. Au-delà, elle est à nouveau condensée : seuls les détails sont réduits, les événements ne sont pas perdus.
- **Il vous prévient quand il faut attendre** : si la mémoire de la conversation précédente n'a pas encore fini d'être mise à jour, la nouvelle conversation affiche « Relecture des conversations précédentes… » pendant 90 secondes au maximum.
- **Vous pouvez la consulter, la modifier et l'effacer** : dans « Paramètres → Mémoire à long terme → Ce que l'IA retient de vous ». Ce que vous modifiez sera pris en compte à l'avenir ; une fois effacée, les anciennes conversations ne seront plus reprises pour être résumées de nouveau.
- Pendant leur travail, les membres notent aussi les faits qui valent la peine d'être retenus, et les retrouvent automatiquement la fois suivante. Si vous choisissez un modèle d'embedding, ils peuvent aussi retrouver d'anciennes conclusions formulées avec d'autres mots.

## 8. Faire plusieurs choses à la fois

- Plusieurs conversations peuvent avancer en même temps sans s'attendre : si l'une attend votre réponse à une question, l'autre continue de travailler.
- Vous pouvez ouvrir plusieurs fenêtres pour un même dossier (Ctrl+Shift+N).
- Ce qu'une conversation a appris, les autres conversations le savent à leur prochain démarrage (voir la section 7).

## 9. Utilisation de l'ordinateur

- Disponible dès le départ : captures d'écran, souris, clavier, ouverture et fermeture de programmes, terminal, sur toutes les fenêtres (sauf celles de Lumen lui-même). Donnez le nom d'un programme ou son chemin complet, et il peut l'ouvrir.
- Demande-t-il votre accord avant d'agir ? Cela dépend du mode d'approbation (section 3).
- **Mode de fonctionnement** : au départ, il agit en arrière-plan et n'accapare ni votre souris ni votre clavier. Pour les jeux et autres cas où il faut une vraie souris, passez en premier plan dans « Paramètres → Utilisation de l'ordinateur ».
- **Arrêt d'urgence** : appuyez sur `Ctrl+Alt+End`, ou poussez la souris dans le coin supérieur gauche de l'écran.
- Vous ne voulez pas que l'IA touche à l'ordinateur ? Activez « Interdire l'utilisation de l'ordinateur » dans « Paramètres → Utilisation de l'ordinateur ».

## 10. Quand il faut les droits administrateur

Les dossiers système comme `C:\Windows` ou `Program Files` exigent les droits administrateur. Si Windows affiche « Accès refusé », l'IA relance la commande en tant qu'administrateur. Windows affiche alors sa propre fenêtre de confirmation, et c'est à vous de décider si vous l'autorisez.

## 11. Tests automatiques

Dans « Paramètres → Tests automatiques », indiquez la commande de test du projet (ou cliquez sur « Détecter automatiquement »). Lorsque l'équipe modifie le code, le système lance les tests avant de commencer, après chaque modification et avant de rendre le travail. Ces tests sont lancés par le système lui-même : ils ne passent pas par un modèle et ne consomment aucun token. Si quelqu'un casse un test qui passait auparavant, il est signalé immédiatement. Il est conseillé de faire un commit git avant de commencer : vous voyez à tout moment ce qui a changé, et vous pouvez revenir en arrière.

## 12. Langue de l'interface

English, Français, Español, Deutsch, Italiano, Português, 简体中文 : 7 langues au total. Changez-la dans « Paramètres → Apparence ». Le changement est immédiat, y compris pour la fenêtre d'outil à droite. L'IA répond dans la langue dans laquelle vous écrivez.

## 13. Vue d'ensemble des paramètres

- **Services et clés** : connectez autant de services d'IA que vous voulez. Les clés sont conservées uniquement dans le Gestionnaire d'identification Windows, jamais dans un fichier de configuration.
- **Modèles d'IA** : quel service et quel modèle utilise chaque membre, à quel point il réfléchit, et quel modèle de secours prendre en cas d'erreur.
- **Mémoire à long terme** : interrupteur de rappel, « Ce que l'IA retient de vous », rappel par le sens.
- **Tests automatiques** et **Utilisation de l'ordinateur** : voir plus haut.
- **Apparence** : langue, fond d'écran, taille de police, couleur d'accent, etc. Les changements s'appliquent immédiatement.
- **Utilisation** : le nombre de tokens consommés aujourd'hui, sur sept jours et au total.
- **Guide des fonctions** : c'est cette page.

## 14. Petites fonctions pratiques

- **Ctrl+K** : une seule zone pour tout trouver : conversations, pages, actions ; à partir de deux caractères, elle retrouve même ce qui a été dit dans les conversations. **Ctrl+/** affiche tous les raccourcis.
- **Ctrl+N** nouvelle conversation, **Ctrl+B** réduit ou affiche la colonne de gauche, **Ctrl+F** cherche dans la conversation, **Ctrl+,** ouvre les paramètres.
- **Clic droit sur une conversation** : renommer, exporter en Markdown, replier dans la liste (sans supprimer).
- **Messages types** : rédigez un texte, appuyez sur Ctrl+S pour l'enregistrer comme message type, puis tapez / dans une zone de saisie vide pour le retrouver. Un message non envoyé est conservé même si vous fermez la fenêtre.
- **Rappel de fin** : si la fenêtre n'est pas au premier plan, la barre des tâches clignote quand la réponse est prête, et un rappel apparaît en bas à droite.
- **Navigateur** : l'étoile met la page en favori, Ctrl+Shift+T rouvre un onglet fermé, la bulle envoie la page à Lumen.
- **Terminal** : faites un clic droit sur une sortie pour envoyer à Lumen la sélection ou la dernière sortie.

## 15. Sécurité et confidentialité

- Vous choisissez tous les modèles : Lumen ne les change jamais de lui-même.
- Vos conversations, votre mémoire et vos journaux sont conservés sur votre ordinateur (dans le dossier `~/.codedoctor`).
- Les clés ne sont conservées que dans le Gestionnaire d'identification Windows ; aucune clé n'est enregistrée dans la mémoire.
- L'IA ne fait pas à votre place les opérations de paiement ni de connexion.

## 16. Conseils

- Plus votre demande est précise, plus le premier résultat sera proche de ce que vous voulez ; si elle est vague, ce n'est pas grave, Lumen vous posera d'abord des questions.
- Pour aller plus vite et consommer moins, choisissez un modèle plus petit ou un niveau de réflexion plus bas ; réservez les grands modèles aux tâches difficiles.
- En cas de plantage, envoyez le fichier `~/.codedoctor/crash.log` au développeur.
