# 💸 Daily Expense Tracker

A simple daily expense tracker built with Python (Flask) and MongoDB.

## Stack
- **Backend**: Python + Flask
- **Database**: MongoDB (via PyMongo)
- **Frontend**: Plain HTML + CSS (served by Flask)

## Features
- Add expenses with title, amount, and category
- View all expenses with a running total
- Delete any expense

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/prithamnandavaram/daily-expense-tracker.git
cd daily-expense-tracker

# 2. Create virtual env & install deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Set up .env
echo "MONGO_URI=mongodb://localhost:27017/expenses_db" > .env

# 4. Make sure MongoDB is running, then start
python app.py
```

Open **http://127.0.0.1:5000**
