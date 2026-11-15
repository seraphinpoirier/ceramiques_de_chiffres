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
chargement dans la table `Candidats` : ces retours restent exclus des analyses
classiques, y compris les cartes. Les autres participations restent incluses.

La catégorie « Les revenants » est distincte de ces analyses : elle compte les
retours de `ALLSTARS` liés par nom et saison initiale, ainsi que les retours
`CB? = O` des saisons classiques grâce à leur colonne `SAISON ORIGINALE`.
La comparaison ignore la casse, les accents et les espaces superflus ; les
correspondances sans saison initiale, ambiguës ou de genre différent ne sont pas attribuées. Le
fichier `candidats_non_identifies.txt` est régénéré au chargement et liste
ces participations non liées, notamment les saisons initiales de `ALLSTARS`.
La liste regroupe par nombre de participations les cinq premières personnes par
genre et toutes les égalités à la cinquième place. Elle indique le classement
et les abandons connus ; les participations non liées en sont exclues.

Les statistiques All Stars utilisent toutes les lignes de la feuille
`ALLSTARS`, y compris les personnes non liées à une saison initiale. Elles
reprennent les mêmes règles pour les premiers éliminés et les finales à deux :
les saisons sans deux ou trois tribus initiales, ainsi que les finales dont le
classement n'est pas renseigné, ne sont pas comptées dans ces graphiques.
L'orientation et les victoires sont comptées selon les données renseignées.
Deux camemberts montrent les tranches d'âge des premiers éliminés par genre,
en excluant les âges inconnus.

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