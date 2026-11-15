# la_tele_en_data

## Mettre à jour les données

Après modification de `data/donnees_kohlanta.xlsx`, reconstruire la base puis
les fichiers JSON depuis la racine du projet :

```bash
python scripts/load_data.py
python scripts/update_data.py
python -m http.server 8000
```

Le chargement de la base nécessite `openpyxl`. Ouvrir ensuite
http://localhost:8000 ; D3 et les données géographiques nécessitent une connexion
Internet. Pour régénérer uniquement les JSON après une modification directe de
la base, exécuter seulement `python scripts/update_data.py`.

Les lignes marquées `CB? = O` dans le fichier source sont exclues lors du
chargement : les retours ne figurent ni dans la base reconstruite ni dans les
analyses, y compris les cartes. Les autres participations restent incluses.

Les graphiques d'âge comptent les participations dont l'âge est connu ; leurs
barres empilent les genres et leurs moyennes utilisent le même périmètre,
globalement et par genre. Survoler ou sélectionner une barre affiche les noms,
saisons et classements du groupe étudié ; cliquer verrouille la sélection.
Le graphique récapitulatif compare les âges minimum, moyen et maximum de ces
groupes sur une échelle commune.

Les finales utilisent les participations classées 1 ou 2, sauf « Totem Maudit »
dont la finale comptait trois personnes. Les égalités correspondent à deux
premières places. Les comparaisons d'âge des finales mixtes excluent les âges
inconnus ou égaux et utilisent le nombre de finales de chaque groupe comme
dénominateur. Les graphiques d'élimination comptent les participations avec
`ori = 1` et `pot != 1` (y compris les valeurs manquantes), celles classées
troisièmes et celles avec `amb = 1`, respectivement.
Pour les
premiers éliminés, seules les saisons comptant deux ou trois valeurs de tribu
sont retenues. Dans chaque tribu, le plus mauvais classement hors abandon est
sélectionné ; une égalité ou l'absence de candidat admissible provoque une
erreur de génération. Les répartitions d'âge par genre excluent les âges
inconnus et regroupent les âges en tranches de 18–25, 26–35, 36–45 et 46 ans
ou plus. Une tranche supplémentaire apparaît si un âge est inférieur à 18 ans.
Les camemberts comparent les premiers éliminés de chaque genre à toutes les
participations de ce genre ; ils montrent des distributions, pas des taux
d'élimination par âge.
Les couleurs sont documentées dans [docs/COLORS.md](docs/COLORS.md).