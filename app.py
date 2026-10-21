from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
import os

load_dotenv()

app = Flask(__name__)
client = MongoClient(os.getenv("MONGO_URI"))
db = client.expenses_db
expenses = db.expenses


@app.route("/")
def index():
    all_expenses = list(expenses.find().sort("_id", -1))
    total = sum(e["amount"] for e in all_expenses)
    return render_template("index.html", expenses=all_expenses, total=total)


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title")
    amount = float(request.form.get("amount", 0))
    category = request.form.get("category")
    if title and amount:
        expenses.insert_one({"title": title, "amount": amount, "category": category})
    return redirect(url_for("index"))


@app.route("/delete/<id>")
def delete(id):
    expenses.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
