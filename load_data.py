"""
load_data.py — Data Engineering Pipeline for MovieLens 25M Dataset into MongoDB.

ETL Workflow:
1. Ingestion: Reads MovieLens 25M CSVs directly from zip archive (or downloads if missing).
2. Cleaning & Preprocessing:
   - Extracts 4-digit release year from movie titles into integer field.
   - Cleans movie titles by removing the year suffix.
   - Normalizes genres string into an array of distinct genres.
   - Enriches movies with IMDb and TMDb IDs from links.csv.
3. Schema Reorganization & Denormalization:
   - Aggregates 25M ratings into per-movie statistics: avgRating, ratingCount, ratingDistribution.
   - Mapped tag genome scores (15.5M rows) into top-5 relevance tags per movie.
   - Aggregates user tags (1M rows) joined with movie genres to identify the most popular tags per genre.
4. Storage:
   - Stores reorganized collections in MongoDB: movies, genre_tags, genome_tags, ratings, users.
   - Creates indexes on movieId, year, genres, ratingCount, avgRating, username.
5. Seeds Admin and User accounts with hashed passwords.
"""

import os
import sys
import time
import zipfile
import urllib.request
import pandas as pd
import numpy as np
from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOCAL_ZIP = os.path.join(DATA_DIR, "ml-25m.zip")
TMP_ZIP = "/tmp/ml-25m.zip"
DOWNLOAD_URL = "https://files.grouplens.org/datasets/movielens/ml-25m.zip"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "movielens")


def get_zip_path():
    """Locate or download the MovieLens 25M zip archive."""
    if os.path.exists(TMP_ZIP):
        return TMP_ZIP
    if os.path.exists(LOCAL_ZIP):
        return LOCAL_ZIP
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Downloading MovieLens 25M dataset from {DOWNLOAD_URL}...")
    urllib.request.urlretrieve(DOWNLOAD_URL, LOCAL_ZIP)
    print("Download completed.")
    return LOCAL_ZIP


def run_etl():
    zip_path = get_zip_path()
    print(f"[1/6] Opening archive: {zip_path}")
    t_start = time.time()

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    with zipfile.ZipFile(zip_path) as z:
        # 1. Genome Tags Lookup
        print("[2/6] Loading genome-tags.csv...")
        with z.open("ml-25m/genome-tags.csv") as f:
            df_gt = pd.read_csv(f)
            tag_lookup = df_gt.set_index("tagId")["tag"].to_dict()

        db.genome_tags.drop()
        db.genome_tags.insert_many(df_gt.to_dict("records"))
        db.genome_tags.create_index("tagId", unique=True)
        print(f"  ✓ Loaded {len(df_gt):,} genome tags.")

        # 2. Links Lookup (IMDb / TMDb)
        print("[3/6] Loading links.csv...")
        with z.open("ml-25m/links.csv") as f:
            df_links = pd.read_csv(f)
            df_links["imdbId"] = df_links["imdbId"].astype(str).str.zfill(7)
            df_links["tmdbId"] = df_links["tmdbId"].fillna(0).astype(int).astype(str)
            links_lookup = df_links.set_index("movieId")[["imdbId", "tmdbId"]].to_dict("index")
        print(f"  ✓ Loaded {len(df_links):,} movie links.")

        # 3. Clean Movies
        print("[4/6] Processing and cleaning movies.csv...")
        with z.open("ml-25m/movies.csv") as f:
            df_movies = pd.read_csv(f)

        # Preprocessing: extract year, clean title, split genres
        df_movies["year"] = df_movies["title"].str.extract(r"\((\d{4})\)$")[0]
        df_movies["year"] = pd.to_numeric(df_movies["year"], errors="coerce")
        df_movies["title_clean"] = df_movies["title"].str.replace(r"\s*\(\d{4}\)$", "", regex=True).str.strip()
        df_movies["genre_list"] = df_movies["genres"].apply(
            lambda g: [x.strip() for x in g.split("|")] if g and g != "(no genres listed)" else []
        )

        # 4. Genome Scores -> Top-5 tags per movie
        print("[5/6] Processing genome-scores.csv to extract top-5 relevant tags per movie...")
        movie_top_tags = {}
        # genome-scores is ~15.5M rows, 1,128 rows per movie sorted by movieId
        chunksize = 1_128_000  # exactly 1,000 movies per chunk
        with z.open("ml-25m/genome-scores.csv") as f:
            for chunk in pd.read_csv(f, chunksize=chunksize, usecols=["movieId", "tagId", "relevance"]):
                # Get top 5 per movie
                top5 = (
                    chunk.sort_values(["movieId", "relevance"], ascending=[True, False])
                    .groupby("movieId", sort=False)
                    .head(5)
                )
                for mid, group in top5.groupby("movieId", sort=False):
                    movie_top_tags[int(mid)] = [
                        {"tag": tag_lookup.get(int(row["tagId"]), f"tag_{row['tagId']}"), "relevance": round(float(row["relevance"]), 4)}
                        for _, row in group.iterrows()
                    ]
        print(f"  ✓ Extracted top-5 genome tags for {len(movie_top_tags):,} movies.")

        # 5. Ratings Aggregation -> Per-movie distribution, count, average rating
        print("[6/6] Aggregating 25M ratings into per-movie distributions and averages...")
        dist_chunks = []
        sample_ratings = []
        with z.open("ml-25m/ratings.csv") as f:
            for i, chunk in enumerate(pd.read_csv(f, chunksize=5_000_000, usecols=["userId", "movieId", "rating"])):
                # Keep first 25,000 ratings for raw ratings collection sample
                if i == 0:
                    sample_ratings = chunk.head(25_000).to_dict("records")
                # Group by movieId and rating value
                grp = chunk.groupby(["movieId", "rating"]).size()
                dist_chunks.append(grp)
                print(f"  Processed {((i + 1) * 5):,}M ratings...")

        total_dist = pd.concat(dist_chunks).groupby(["movieId", "rating"]).sum()

        # Build movie stats dictionary
        movie_stats = {}
        valid_ratings = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

        for (mid, rat), count in total_dist.items():
            mid = int(mid)
            if mid not in movie_stats:
                movie_stats[mid] = {
                    "count": 0,
                    "sum": 0.0,
                    "dist": {str(r): 0 for r in valid_ratings},
                }
            movie_stats[mid]["count"] += int(count)
            movie_stats[mid]["sum"] += float(rat) * int(count)
            rat_str = str(float(rat))
            if rat_str in movie_stats[mid]["dist"]:
                movie_stats[mid]["dist"][rat_str] += int(count)

        print(f"  ✓ Aggregated rating stats for {len(movie_stats):,} movies.")

        # 6. Popular tags per genre from tags.csv
        print("Computing most popular tags per genre from tags.csv...")
        with z.open("ml-25m/tags.csv") as f:
            df_tags = pd.read_csv(f, usecols=["movieId", "tag"]).dropna()

        df_exploded = df_movies[["movieId", "genre_list"]].explode("genre_list").dropna()
        df_exploded.rename(columns={"genre_list": "genre"}, inplace=True)
        merged_tags = pd.merge(df_tags, df_exploded, on="movieId")
        merged_tags["tag_clean"] = merged_tags["tag"].astype(str).str.lower().str.strip()

        genre_tag_counts = (
            merged_tags.groupby(["genre", "tag_clean"])
            .size()
            .reset_index(name="count")
            .sort_values(["genre", "count"], ascending=[True, False])
        )

        genre_tag_docs = []
        for genre, group in genre_tag_counts.groupby("genre"):
            top_tag = group.iloc[0]["tag_clean"]
            top_count = int(group.iloc[0]["count"])
            top_5 = [
                {"tag": row["tag_clean"], "count": int(row["count"])}
                for _, row in group.head(5).iterrows()
            ]
            genre_tag_docs.append({
                "genre": str(genre),
                "topTag": str(top_tag),
                "count": top_count,
                "topTags": top_5,
            })

        db.genre_tags.drop()
        if genre_tag_docs:
            db.genre_tags.insert_many(genre_tag_docs)
            db.genre_tags.create_index("genre", unique=True)
        print(f"  ✓ Stored popular tags for {len(genre_tag_docs)} genres in genre_tags collection.")

        # 7. Assemble movie documents and insert
        print("Building reorganized movies collection...")
        movie_docs = []
        for _, row in df_movies.iterrows():
            mid = int(row["movieId"])
            stats = movie_stats.get(mid, {
                "count": 0,
                "sum": 0.0,
                "dist": {str(r): 0 for r in valid_ratings},
            })
            links = links_lookup.get(mid, {"imdbId": "", "tmdbId": ""})
            avg_rating = round(stats["sum"] / stats["count"], 2) if stats["count"] > 0 else 0.0

            doc = {
                "movieId": mid,
                "title": str(row["title_clean"]),
                "fullTitle": str(row["title"]),
                "year": int(row["year"]) if pd.notnull(row["year"]) else None,
                "genres": row["genre_list"],
                "imdbId": links.get("imdbId", ""),
                "tmdbId": links.get("tmdbId", ""),
                "avgRating": avg_rating,
                "ratingCount": stats["count"],
                "ratingDistribution": stats["dist"],
                "topTags": movie_top_tags.get(mid, []),
            }
            movie_docs.append(doc)

        db.movies.drop()
        batch_size = 5000
        for i in range(0, len(movie_docs), batch_size):
            db.movies.insert_many(movie_docs[i : i + batch_size])
        print(f"  ✓ Inserted {len(movie_docs):,} movies.")

        # 8. Raw / Sample Ratings collection
        print("Populating ratings collection with initial data...")
        db.ratings.drop()
        if sample_ratings:
            db.ratings.insert_many(sample_ratings)
            print(f"  ✓ Inserted {len(sample_ratings):,} baseline rating documents.")

        # 9. Seed Users
        print("Seeding administrative and regular user accounts...")
        db.users.drop()
        db.users.insert_many([
            {
                "username": "admin",
                "password": generate_password_hash("admin123"),
                "role": "admin",
                "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "username": "user",
                "password": generate_password_hash("user123"),
                "role": "user",
                "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        ])
        db.users.create_index("username", unique=True)
        print("  ✓ Seeded accounts: admin (admin/admin123) and user (user/user123).")

        # 10. Create Performance Indexes
        print("Creating MongoDB performance indexes...")
        db.movies.create_index("movieId", unique=True)
        db.movies.create_index([("title", "text")])
        db.movies.create_index([("year", ASCENDING), ("ratingCount", DESCENDING)])
        db.movies.create_index([("ratingCount", DESCENDING), ("avgRating", DESCENDING)])
        db.movies.create_index("genres")
        db.ratings.create_index([("movieId", ASCENDING), ("userId", ASCENDING)])
        db.ratings.create_index("username")
        print("  ✓ Indexes created successfully.")

    elapsed = time.time() - t_start
    print(f"\n✨ MovieLens ETL Pipeline completed successfully in {elapsed:.1f} seconds!")
    client.close()


if __name__ == "__main__":
    run_etl()
