import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set a nice theme for the plots
sns.set_theme(style="whitegrid")

print("Loading data...")
interactions = pd.read_csv('data/interactions_train.csv')
items = pd.read_csv('data/items.csv')

print(f"Total interactions: {len(interactions)}")
print(f"Total unique books: {len(items)}\n")

# ==========================================
# Plot 1: User Activity Distribution
# ==========================================
user_activity = interactions.groupby('u').size()
plt.figure(figsize=(10, 5))
sns.histplot(user_activity, bins=50, color='blue', kde=False)
plt.title('User Activity: Books per User')
plt.xlabel('Number of Borrowed Books')
plt.ylabel('Number of Users')
plt.xlim(0, 50) # Limit x-axis to filter out extreme outliers
plt.show()

# ==========================================
# Plot 2: Item Popularity (Long Tail)
# ==========================================
item_popularity = interactions.groupby('i').size().sort_values(ascending=False).values
plt.figure(figsize=(10, 5))
plt.plot(item_popularity, color='red')
plt.fill_between(range(len(item_popularity)), item_popularity, color='red', alpha=0.3)
plt.title('Item Popularity (Long Tail Distribution)')
plt.xlabel('Item Index (from most to least popular)')
plt.ylabel('Number of Interactions')
plt.show()

# ==========================================
# Plot 3: Missing Metadata (Crucial for Data Augmentation)
# ==========================================
missing_percent = (items.isnull().sum() / len(items)) * 100
plt.figure(figsize=(10, 5))
sns.barplot(x=missing_percent.index, y=missing_percent.values, palette='viridis')
plt.title('Percentage of Missing Values in Book Metadata')
plt.ylabel('% Missing')
plt.show()


print(user_activity.value_counts().head(10).sort_index())