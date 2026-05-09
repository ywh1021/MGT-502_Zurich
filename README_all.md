# Book Recommendation System

[![Leaderboard Score](https://img.shields.io/badge/Leaderboard-0.1452%2B-green)](#performance-summary)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

> **Project Video Presentation:** [Link to your video here]

## 1. Project Overview
This project implements a hybrid recommendation engine for a library dataset. The goal is to achieve a Precision@10 score higher than **0.1452** on the competition leaderboard by leveraging collaborative filtering and advanced machine learning techniques.

---

## 2. Exploratory Data Analysis (EDA)

We use two main datasets to build our recommendation model. The first one is the interaction dataset with 87,047 interactions across 7,838 users and 15,291 books with timestamps for each interaction. The second dataset is a list of 15,291 books with title, author, publisher, subjects, and ISBN provided for each book. In advance to constructing our interaction model, it would be useful to conduct exploratory data analysis to understand our datasets better.

### Missing Values in the Books Dataset
In advance of diving into the EDA process, it is crucial to address the completeness of our book metadata. A preliminary check reveals a notable proportion of missing values across key attributes:
*   Author: 17.35% missing
*   Subject: 14.54% missing
*   ISBN: 4.73% missing
*   Publisher: 0.16% missing
While pure collaborative filtering (CF) models rely solely on user-item interaction matrices and remain unaffected by these gaps, such metadata becomes vital when developing advanced hybrid or content-based models. To build a more robust recommendation system moving forward, we can leverage the available ISBN data and try to query external databases via open-source APIs, allowing us to impute the missing authors and subjects effectively.


### EDA with Graphs
*   **Interaction Matrix:** The interaction matrix below provides an initial visual overview of our dataset. A smooth frontier is visible, which is highly unusual of real-world interaction data and strongly suggests that this dataset was synthetically generated. Furthermore, we observe that users with higher IDs exhibit a broader range of book interactions across the item spectrum. Conversely, users with IDs below 2,000 interact more densely but are confined to a limited subset of books. While recommending based on this mathematical boundary could inflate our prediction scores, we have intentionally chosen to ignore this artifact. Exploiting it would lead to a model that fails to generalize to real-world recommendation scenarios.
    
    <img src="./images/interaction.jpeg" width="500">
    
*   **User Activity:** From the bar chart demonstrated below, the majority of the users read fewer than 10 books. Although we still have some readers who interact with over 300 books, 69.06% users interact with less and 10 books, and 40.79% of the readers interact with even fewer than 5 books. Due to a lack of interaction data for many users, standard user-based collaborative filtering will struggle to find similar peers for these inactive users. To address this "cold-start" issue, our model will likely need to rely on hybrid approaches, incorporating book content features or baseline popularity metrics for early recommendations.

    <img src="./images/user_activity_4.jpeg" width="500">

*   **Item Popularity:** This chart reveals a long tail distribution in book interactions. The top 5% popular book account for 23.70% all interactions, while over half (52.23%) have fewer than 5 interactions. While recommend popular books can be useful, we need to be cautious of popularity bias, where the model defaults to suggesting only top hits for everyone. Implementing strategies like item-based collaborative filtering or content-based matching can possibly help us discover relevant hidden gems from the tail.

    <img src="./images/user_plot.jpeg" width="500">

*   **Reader Loyalty:** evaluate author preference, we calculated the 'average books read per author' for 4,641 active users (those with ≥ 5 read books). The resulting chart displays a heavily right-skewed distribution. The dominant peak at 1.0 indicates that most users are "Pure Explorers," typically consuming only one book per author. Conversely, the extended right tail reveals a dedicated segment of "Loyal Fans," with 20.2% of active users reading multiple works (≥ 2) by the same author. This behavioral divide suggests a dual recommendation strategy: leveraging collaborative filtering to capture the diverse, cross-author tastes of the majority, while integrating author-based content features to satisfy the specific preferences of niche loyalists.
  
    <img src="./images/reader_loyalty.jpeg" width="500"> 

---

## 3. Data Augmentation
To improve recommendation quality, we enriched the original metadata using external sources:
*   **Google Books API:** Fetched missing descriptions and categories.
*   **ISBNDB:** (Optional) Supplemented publisher and language data.
*   **Feature Engineering:** Combined original metadata with augmented text data for content-based signals.

---

## 4. Model Architectures & Experiments

### Performance Summary (Validation Results)
| Technique | Precision@10 | Recall@10 |
| :--- | :--- | :--- |
| **User-User CF** | 0.0477 | 0.2616 |
| **Item-Item CF** | 0.0477 | 0.2359 |
| **User & Item Hybrid** | 0.0524 | 0.2681 |
| **U + I + Content** | **0.XXXX** | **0.XXXX** |
| **U + I + Content + Pop + Time decay** | **0.XXXX** | **0.XXXX** |
| **XGBoost** | **0.XXXX** | **0.XXXX** |

### Model Description
*   **User-User:** 
*   **Item-Item:** 
*   **User & Item Hybrid:** 
*   **U + I + Content:**
*   **U + I + Content + Pop + Time decay:**
*   **XGBoost:**


### Hyper-parameter Optimization
We used [Method, e.g., Optuna / GridSearch] to tune:
*   K-neighbors for CF models.
*   Learning rates and depth for Boosting models.
*   Embedding dimensions for Matrix Factorization.

> **Note:** The above results are calculated using Cross-Validation on the training set to ensure label integrity.

---

## 5. Evaluation: The Best Model
The **[Insert Best Model Name, e.g., XGBoost Hybrid]** outperformed others by integrating collaborative signals with item metadata. 

### Good vs. Bad Predictions
#### Good Predictions
*   **User A History:** [List 1-2 genres/books]
*   **Recommendation:** [Book X]
*   **Why it works:** Align with the user's preference for [Genre].

#### Bad Predictions
*   **User B History:** [List 1-2 genres/books]
*   **Recommendation:** [Book Y]
*   **Why it failed:** Likely due to [Reason, e.g., Popularity bias or niche interest].

---

## 6. How to Run the Code
```bash
# Clone the repository
git clone [https://github.com/your-username/your-repo.git](https://github.com/your-username/your-repo.git)

# Install dependencies
pip install -r requirements.txt

# Run the training & evaluation script
python main.py
