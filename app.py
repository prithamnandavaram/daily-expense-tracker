"""
app.py — Production-Grade Flask Application for MovieLens Analytics Dashboard.

Course: DS5003 Data Engineering Lab
Institution: IIT Palakkad
Instructor: Dr. Koninika Pal

Features:
- MongoDB Backend (NoSQL schema optimization & denormalization)
- Role-Based Access Control (Admin vs Regular User)
- Interactive Charts & Visualizations answering all 7 Lab Questions (a)-(g)
- Real-Time User Rating Submission & Live Metric Recalculation
- Admin Management Console (Database Stats, User Roles, Activity Audit)
- Interactive In-App Presentation Slides for Project Demo (Deliverable 1)
"""

import os
import time
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "movielens-ds5003-secure-key-2026")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "movielens")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


# ---------------------------------------------------------------------------
# Authentication & Authorization Helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Administrator privileges required.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.users.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            session["role"] = user.get("role", "user")
            flash(f"Welcome back, {username}! Logged in as {session['role']}.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))

        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")
        if len(password) < 4:
            flash("Password must be at least 4 characters.", "error")
            return render_template("register.html")

        if db.users.find_one({"username": username}):
            flash("Username already exists. Please choose another.", "error")
            return render_template("register.html")

        db.users.insert_one({
            "username": username,
            "password": generate_password_hash(password),
            "role": "user",
            "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        flash("Registration successful! You may now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Application Views
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/admin")
@admin_required
def admin_panel():
    return render_template("admin.html")


@app.route("/slides")
@login_required
def presentation_slides():
    """Deliverable 1: Interactive project presentation slides."""
    return render_template("slides.html")


# ---------------------------------------------------------------------------
# Analytics API Endpoints (Questions a - g)
# ---------------------------------------------------------------------------

# Search movies autocomplete
@app.route("/api/movies/search")
@login_required
def api_movie_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    results = list(
        db.movies.find(
            {"title": {"$regex": q, "$options": "i"}},
            {"_id": 0, "movieId": 1, "title": 1, "fullTitle": 1, "year": 1, "avgRating": 1, "ratingCount": 1},
        )
        .sort("ratingCount", -1)
        .limit(15)
    )
    return jsonify(results)


# (a) For a particular movie, show the top-5 tags based on relevance scores
@app.route("/api/tags/top/<int:movie_id>")
@login_required
def api_top_tags(movie_id):
    movie = db.movies.find_one(
        {"movieId": movie_id},
        {"_id": 0, "movieId": 1, "title": 1, "topTags": 1},
    )
    if not movie or not movie.get("topTags"):
        return jsonify({"movieId": movie_id, "title": movie.get("title", "Unknown") if movie else "Unknown", "tags": []})

    return jsonify({
        "movieId": movie["movieId"],
        "title": movie.get("title", ""),
        "tags": movie["topTags"][:5],
    })


# (b) Show overall and year-wise top 10 movies based on the average rating
@app.route("/api/movies/top_rated")
@login_required
def api_top_rated():
    year_param = request.args.get("year", "").strip()

    if year_param:
        try:
            year = int(year_param)
            # Threshold to ensure statistical significance
            query = {"year": year, "ratingCount": {"$gte": 20}}
            results = list(
                db.movies.find(
                    query,
                    {"_id": 0, "movieId": 1, "title": 1, "year": 1, "avgRating": 1, "ratingCount": 1},
                )
                .sort([("avgRating", DESCENDING), ("ratingCount", DESCENDING)])
                .limit(10)
            )
            # If historical year has fewer movies with 20 ratings, fall back to >= 5
            if len(results) < 5:
                results = list(
                    db.movies.find(
                        {"year": year, "ratingCount": {"$gte": 5}},
                        {"_id": 0, "movieId": 1, "title": 1, "year": 1, "avgRating": 1, "ratingCount": 1},
                    )
                    .sort([("avgRating", DESCENDING), ("ratingCount", DESCENDING)])
                    .limit(10)
                )
        except ValueError:
            return jsonify({"error": "Invalid year format"}), 400
    else:
        # Overall top 10 with minimum 500 ratings for credibility
        results = list(
            db.movies.find(
                {"ratingCount": {"$gte": 500}},
                {"_id": 0, "movieId": 1, "title": 1, "year": 1, "avgRating": 1, "ratingCount": 1},
            )
            .sort([("avgRating", DESCENDING), ("ratingCount", DESCENDING)])
            .limit(10)
        )

    return jsonify(results)


# (c) What are the most popular tags given for each genre
@app.route("/api/tags/genre")
@login_required
def api_tags_by_genre():
    results = list(
        db.genre_tags.find(
            {},
            {"_id": 0, "genre": 1, "topTag": 1, "count": 1, "topTags": 1},
        ).sort("genre", ASCENDING)
    )
    return jsonify(results)


# (d) For a particular movie, show the distribution of users’ ratings
@app.route("/api/ratings/distribution/<int:movie_id>")
@login_required
def api_rating_distribution(movie_id):
    movie = db.movies.find_one(
        {"movieId": movie_id},
        {"_id": 0, "movieId": 1, "title": 1, "year": 1, "avgRating": 1, "ratingCount": 1, "ratingDistribution": 1},
    )
    if not movie:
        return jsonify({"error": "Movie not found"}), 404

    # Check if current user has rated this movie
    user_rating_doc = db.ratings.find_one(
        {"movieId": movie_id, "username": session.get("user")},
        {"_id": 0, "rating": 1},
    )
    user_rating = user_rating_doc["rating"] if user_rating_doc else None

    # Format distribution array
    ratings_order = ["0.5", "1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0"]
    dist = movie.get("ratingDistribution", {})
    distribution_list = [
        {"rating": float(r), "label": f"{r} ★", "count": int(dist.get(r, 0))}
        for r in ratings_order
    ]

    return jsonify({
        "movieId": movie["movieId"],
        "title": movie.get("title", ""),
        "year": movie.get("year"),
        "avgRating": movie.get("avgRating", 0.0),
        "ratingCount": movie.get("ratingCount", 0),
        "userRating": user_rating,
        "distribution": distribution_list,
    })


# (e) Show the distribution of total ratings for movies
@app.route("/api/ratings/total_distribution")
@login_required
def api_total_rating_distribution():
    # Distribution of movie popularity (how many movies fall in each rating count bracket)
    pipeline = [
        {"$match": {"ratingCount": {"$gt": 0}}},
        {
            "$bucket": {
                "groupBy": "$ratingCount",
                "boundaries": [1, 10, 50, 100, 500, 1000, 5000, 10000, 50000],
                "default": "50000+",
                "output": {"count": {"$sum": 1}},
            }
        },
    ]
    raw_buckets = list(db.movies.aggregate(pipeline))

    range_labels = {
        1: "1 – 9",
        10: "10 – 49",
        50: "50 – 99",
        100: "100 – 499",
        500: "500 – 999",
        1000: "1,000 – 4,999",
        5000: "5,000 – 9,999",
        10000: "10,000 – 49,999",
        "50000+": "50,000+",
    }

    formatted = []
    for b in raw_buckets:
        _id = b["_id"]
        label = range_labels.get(_id, str(_id))
        formatted.append({"range": label, "count": b["count"]})

    return jsonify(formatted)


# (f) For a particular year, show which genre released the highest number of movies
@app.route("/api/genres/releases")
@login_required
def api_genre_releases():
    year = request.args.get("year", type=int)
    if not year:
        return jsonify({"error": "year parameter required"}), 400

    pipeline = [
        {"$match": {"year": year}},
        {"$unwind": "$genres"},
        {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "genre": "$_id", "count": 1}},
    ]
    results = list(db.movies.aggregate(pipeline))
    return jsonify({"year": year, "releases": results})


# (g) Show genre-wise coverage of movies
@app.route("/api/genres/coverage")
@login_required
def api_genre_coverage():
    pipeline = [
        {"$unwind": "$genres"},
        {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "genre": "$_id", "count": 1}},
    ]
    results = list(db.movies.aggregate(pipeline))
    return jsonify(results)


# ---------------------------------------------------------------------------
# Interactive Features: User Rating Modification (Regulation 4)
# ---------------------------------------------------------------------------

@app.route("/api/ratings/submit", methods=["POST"])
@login_required
def api_submit_rating():
    data = request.get_json() or {}
    movie_id = data.get("movieId")
    rating_val = data.get("rating")

    if not movie_id or rating_val is None:
        return jsonify({"error": "movieId and rating are required"}), 400

    try:
        movie_id = int(movie_id)
        rating_val = float(rating_val)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid format for movieId or rating"}), 400

    if rating_val < 0.5 or rating_val > 5.0 or (rating_val * 2) % 1 != 0:
        return jsonify({"error": "Rating must be between 0.5 and 5.0 in 0.5 steps"}), 400

    username = session.get("user")
    movie = db.movies.find_one({"movieId": movie_id})
    if not movie:
        return jsonify({"error": "Movie not found"}), 404

    # Check if user already rated this movie
    existing_rating = db.ratings.find_one({"movieId": movie_id, "username": username})

    rating_str = str(rating_val)
    dist = movie.get("ratingDistribution", {})
    count = movie.get("ratingCount", 0)
    current_avg = movie.get("avgRating", 0.0)
    total_sum = current_avg * count

    if existing_rating:
        old_val = float(existing_rating["rating"])
        old_str = str(old_val)
        # Adjust distribution
        if old_str in dist and dist[old_str] > 0:
            dist[old_str] -= 1
        dist[rating_str] = dist.get(rating_str, 0) + 1
        total_sum = total_sum - old_val + rating_val
        new_avg = round(total_sum / count, 2) if count > 0 else rating_val
    else:
        # New rating
        dist[rating_str] = dist.get(rating_str, 0) + 1
        count += 1
        total_sum += rating_val
        new_avg = round(total_sum / count, 2)

    # Persist in user ratings collection
    db.ratings.update_one(
        {"movieId": movie_id, "username": username},
        {
            "$set": {
                "movieId": movie_id,
                "username": username,
                "rating": rating_val,
                "timestamp": int(time.time()),
            }
        },
        upsert=True,
    )

    # Update denormalized movie document
    db.movies.update_one(
        {"movieId": movie_id},
        {
            "$set": {
                "avgRating": new_avg,
                "ratingCount": count,
                "ratingDistribution": dist,
            }
        },
    )

    return jsonify({
        "ok": True,
        "message": f"Rating of {rating_val} ★ successfully saved for '{movie['title']}'!",
        "newAvg": new_avg,
        "newCount": count,
    })


# ---------------------------------------------------------------------------
# Administrative & Utility Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/years")
@login_required
def api_years():
    years = db.movies.distinct("year")
    filtered = sorted([int(y) for y in years if y and y > 1900], reverse=True)
    return jsonify(filtered)


@app.route("/api/admin/stats")
@admin_required
def api_admin_stats():
    total_movies = db.movies.count_documents({})
    total_users = db.users.count_documents({})
    total_genre_tags = db.genre_tags.count_documents({})
    user_ratings_count = db.ratings.count_documents({"username": {"$exists": True}})
    latest_ratings = list(
        db.ratings.find({"username": {"$exists": True}}, {"_id": 0})
        .sort("timestamp", DESCENDING)
        .limit(10)
    )

    return jsonify({
        "totalMovies": total_movies,
        "totalUsers": total_users,
        "totalGenreTags": total_genre_tags,
        "userRatingsCount": user_ratings_count,
        "latestRatings": latest_ratings,
    })


@app.route("/api/admin/users")
@admin_required
def api_admin_users():
    users = list(db.users.find({}, {"_id": 0, "password": 0}).sort("createdAt", DESCENDING))
    return jsonify(users)


@app.route("/api/admin/toggle_role", methods=["POST"])
@admin_required
def api_admin_toggle_role():
    data = request.get_json() or {}
    target_username = data.get("username")
    if not target_username:
        return jsonify({"error": "Target username required"}), 400

    if target_username == session.get("user"):
        return jsonify({"error": "Cannot change your own role"}), 400

    user = db.users.find_one({"username": target_username})
    if not user:
        return jsonify({"error": "User not found"}), 404

    new_role = "admin" if user.get("role") == "user" else "user"
    db.users.update_one({"username": target_username}, {"$set": {"role": new_role}})

    return jsonify({"ok": True, "username": target_username, "newRole": new_role})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
