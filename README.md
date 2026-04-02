# 📈 Mon Portefeuille Boursier — Guide d'installation

## Prérequis
- Python 3.9 ou supérieur
- pip

---

## Installation

### 1. Créer un dossier et placer les fichiers
```
mon_portefeuille/
├── portfolio_tracker.py
├── requirements.txt
└── README.md
```

### 2. (Recommandé) Créer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Lancer l'application
```bash
streamlit run portfolio_tracker.py
```

L'application s'ouvre automatiquement sur http://localhost:8501

---

## Utilisation

### Ajouter une action
1. Dans le panneau de gauche, entrez le **ticker** (ex: MSFT, AAPL, MC.PA, NEM.DE)
2. Choisissez l'**enveloppe** : PEA ou CTO
3. Entrez la **quantité** et le **prix d'achat**
4. Choisissez la **devise d'achat** (EUR ou USD → converti automatiquement)
5. Cliquez sur ✅ Ajouter

### Exemples de tickers
| Action         | Ticker    |
|----------------|-----------|
| Microsoft      | MSFT      |
| Apple          | AAPL      |
| LVMH           | MC.PA     |
| TotalEnergies  | TTE.PA    |
| Nemetschek     | NEM.DE    |
| Air Liquide    | AI.PA     |
| Nvidia         | NVDA      |
| Alphabet       | GOOGL     |

Pour les actions **européennes**, ajouter le suffixe de la bourse :
- Paris : `.PA`
- Frankfurt : `.DE`
- Amsterdam : `.AS`
- Milan : `.MI`

### Supprimer une action
Sélectionnez-la dans le menu déroulant "Supprimer une action" et cliquez sur Supprimer.

### Rafraîchir les prix
Les prix se rafraîchissent automatiquement toutes les **5 minutes**.
Pour forcer une mise à jour : bouton 🔄 Rafraîchir les prix.

---

## Fonctionnalités

- ✅ Ajout / suppression d'actions en temps réel
- ✅ Prix en direct via Yahoo Finance
- ✅ Conversion automatique USD → EUR
- ✅ Séparation PEA / CTO
- ✅ Graphique d'évolution historique (1 mois à 5 ans)
- ✅ Camembert de répartition par action et par enveloppe
- ✅ Barre de performance P&L par action
- ✅ Logos des entreprises automatiques
- ✅ Sauvegarde automatique dans `portfolio_data.json`

---

## Déploiement sur Streamlit Cloud (optionnel)

1. Créez un compte sur https://streamlit.io
2. Poussez vos fichiers sur un repo GitHub privé
3. Connectez le repo sur Streamlit Cloud
4. Votre appli sera accessible depuis n'importe où

---

## Notes
- Les données proviennent de **Yahoo Finance** (gratuites, sans clé API)
- Le fichier `portfolio_data.json` est créé automatiquement dans le même dossier
- Les prix sont indicatifs et ne constituent pas un conseil en investissement
