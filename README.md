# Trader Salma , ENSIM Trade Center (TP2 BI)

Trader automatique pour l'ENSIM Trade Center. Toutes les 30 minutes, un workflow GitHub Actions lit le marché, calcule mon signal et réécrit `decision.json` (une valeur entre -1 et +1 par produit), que le marché de l'organisateur lit à chaque tick.

- **Dashboard :** https://salmazaime.github.io/ensim-trader-salmazaime/
- **Fichier de décision :** https://raw.githubusercontent.com/salmazaime/ensim-trader-salmazaime/main/decision.json

## 1. Pipeline

| Étape | Fichier | Rôle |
|---|---|---|
| Acquisition | `scripts/algorithm.py` → `fetch_json` | flux publics de l'organisateur : `market.json` (prix), `holdings.json` (mon portefeuille), `leaderboard.json` (classement) |
| Signal | `zscore_info` / `compute_signal` | retour à la moyenne par z-score (§2) |
| Garde-fou budget | `apply_budget_guard` (fourni) | un achat ne descend jamais sous 50 € de cash |
| Décision | `decision.json` | lu par le marché à chaque tick |
| Journal | `docs/data/decision_log.json` | décision, raison, portefeuille et classement à chaque exécution |
| Évaluation | `scripts/backtest.py` → `docs/data/backtest.json` | rejeu de l'historique réel contre les 3 baselines |
| Automatisation | `.github/workflows/auto_decide.yml` | toutes les 30 min + lancement manuel |
| Restitution | `docs/index.html` | dashboard Chart.js sur GitHub Pages |

## 2. Mon signal : retour à la moyenne (z-score)

**Ce que j'ai observé avant de choisir.** J'ai comparé 3 familles de stratégies sur les 340 ticks réels, dans les mêmes conditions de départ (1 000 € + 1 000 unités de chaque produit) :

| Famille | Rendement | Conclusion |
|---|---|---|
| Suivi de tendance (moyennes mobiles courte/longue) | **-39 %** | arrive toujours après le retournement |
| Bandes de Bollinger (tout ou rien) | +72 % | fonctionne, mais en tout ou rien |
| **Retour à la moyenne par z-score** | **+84 %** | retenu |

Les prix de ce marché **oscillent autour d'un niveau** au lieu de suivre des tendances durables. Le code public du marché le confirme : chaque nouveau prix est à moitié tiré vers une tendance cyclique. Parier sur le retour vers la moyenne est donc cohérent avec la façon dont le marché fonctionne.

**Comment je décide, à chaque exécution et pour chaque produit :**
1. Je calcule la moyenne et l'écart-type des **20 derniers prix**.
2. `z = (prix actuel − moyenne) / écart-type` mesure à quel point le prix est anormal.
3. `signal = −z`, borné à [-1, +1] :
   - prix au-dessus de la normale (z > 0) : je **vends** ;
   - prix en dessous (z < 0) : j'**achète** ;
   - un écart de 1 écart-type donne déjà un ordre maximal.
4. Si |z| < 0,2, je **ne fais rien** : le prix est dans sa normale, et trader dessus reviendrait à réagir au bruit.

**Pourquoi un signal proportionnel plutôt que Bollinger ?** La taille de l'ordre suit ma conviction : un petit écart donne un petit ordre. Bollinger achète ou vend 100 unités d'un coup dès qu'une bande est franchie. Le z-score fait mieux (+84 % contre +72 %) pour un risque comparable.

## 3. Structure de la décision : exclure avant de comparer

- **Impossible, donc exclu :** vendre plus que je ne possède (le marché le refuse) ; dépenser de l'argent que je n'ai pas (le garde-fou réduit l'achat et garde 50 € de réserve).
- **Exclu pour risque :** trader quand le prix est dans sa zone normale (zone morte |z| < 0,2) ; un ordre maximal ne part que pour un écart d'au moins 1 écart-type.
- **Ce qui reste est comparé :** acheter, vendre ou attendre, selon le z-score.

## 4. Résultats (rejeu de l'historique réel, 340 ticks)

Mêmes règles que le marché. À chaque tick, mon signal ne voit que le passé, et l'ordre s'exécute au prix du tick suivant. Les baselines sont tirées comme dans le code du marché (moyenne de 20 rejeux).

| Trader | Valeur finale | Rendement | Volatilité / tick | Pire perte |
|---|---|---|---|---|
| **Ma stratégie** | **32 238** | **+84,2 %** | 0,91 % | -16,5 % |
| random_trader | 17 525 | +0,1 % | 0,87 % | -16,0 % |
| random_buyer | 17 901 | +2,3 % | 1,21 % | -18,7 % |
| random_seller | 18 060 | +3,2 % | 0,09 % | -0,5 % |
| ne rien faire | 17 838 | +1,9 % | 1,15 % | -17,8 % |

**Ce que j'optimise, et ce que je sacrifie.** Je vise le rendement **par unité de risque**, pas seulement la valeur finale. Mon ratio rendement / volatilité est de 93, contre 36 pour la meilleure baseline.

En contrepartie, random_seller est bien plus stable (pire perte de -0,5 %), parce qu'il convertit presque tout en cash. Ma stratégie garde des produits, donc elle subit leurs baisses. Ma pire perte (-16,5 %) vient du début de l'historique, avant que mes positions aient eu le temps de payer. Ensuite, mes baisses sont plus courtes que celles de random_trader (voir le graphique de drawdown).

## 5. Choix des graphiques du dashboard

| Visuel | Pour qui | Décision | Pourquoi ce type |
|---|---|---|---|
| Cartes KPI | moi, à chaque passage | « je bats le hasard ? » | un chiffre + une comparaison, lisible tout de suite |
| Courbes de valeur (moi + 3 baselines) | moi / l'enseignant | garder ou changer de stratégie | les courbes superposées montrent **quand** et **comment** l'écart se crée |
| Classement réel | moi | où j'en suis sur le vrai marché | un tableau, pour comparer des montants précis |
| Drawdown (perte depuis le plus haut) | moi | « je prends trop de risque ? » | la profondeur donne la pire perte, la largeur le temps de récupération |
| z-score par produit avec les seuils ±1 | moi | comprendre **pourquoi** j'achète ou je vends maintenant | c'est l'indicateur exact de mon algorithme, avec ses seuils de décision |
| Journal des décisions | moi / l'enseignant | expliquer la trajectoire | un tableau chronologique, avec une raison par ligne |

## 6. Limites

- **Inscription :** le marché ne lit que les traders ajoutés par l'organisateur dans son registre. Tant que ce n'est pas fait, le script tourne avec le portefeuille de départ par défaut, et le dashboard l'indique.
- **Mon impact sur les prix n'est pas simulé :** le prix dépend de la demande moyenne de tous les traders. Quand j'achète, je fais un peu monter le prix contre moi, donc le résultat réel sera probablement inférieur au rejeu.
- **Fenêtre fixe de 20 ticks :** le produit C a des cycles courts (environ 24 ticks), donc ma moyenne y est en retard. Une fenêtre adaptée à chaque produit pourrait faire mieux, au risque de sur-ajuster l'historique.
- **Tendance de fond :** si un produit se mettait à monter durablement, le retour à la moyenne vendrait trop tôt. C'est exactement le cas où le suivi de tendance gagnerait.
- **Ticks irréguliers :** le marché ne lit que ma dernière décision au moment du tick.
