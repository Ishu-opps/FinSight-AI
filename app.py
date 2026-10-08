import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

# Initialize Gemini API Client
genai.configure(api_key=app.config['GEMINI_API_KEY'])
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

DEFAULT_CATEGORIES = [
    "Food", "Transportation", "Shopping", "Bills", 
    "Entertainment", "Education", "Medical", "Others"
]

# --- SQLALCHEMY MODELS ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    categories = db.relationship('Category', backref='user', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade="all, delete-orphan")
    reports = db.relationship('Report', backref='user', lazy=True, cascade="all, delete-orphan")

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_name = db.Column(db.String(50), nullable=False)
    monthly_budget = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    current_spent = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    merchant_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False, default='Other')
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    ai_category = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_expense = db.Column(db.Numeric(10, 2), nullable=False)
    total_savings = db.Column(db.Numeric(10, 2), nullable=False)
    monthly_budget = db.Column(db.Numeric(10, 2), nullable=False)
    report_date = db.Column(db.DateTime, default=datetime.utcnow)

# --- GEMINI API INTEGRATION LAYER ---
def ai_categorize_merchant(merchant_name):
    prompt = f"""
    Categorize the merchant/transaction '{merchant_name}' into EXACTLY ONE of the following budget categories:
    {json.dumps(DEFAULT_CATEGORIES)}
    
    Respond STRICTLY in JSON format with no additional markdown, text, or explanations:
    {{"category": "<chosen_category>"}}
    """
    try:
        response = gemini_model.generate_content(prompt)
        text_content = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(text_content)
        category = data.get("category", "Others")
        return category if category in DEFAULT_CATEGORIES else "Others"
    except Exception as e:
        print(f"[Gemini Categorization Error]: {e}")
        return "Others"

# --- HELPER DECORATOR ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'danger')
            return redirect(url_for('register'))
            
        hashed_pwd = generate_password_hash(password, method='scrypt')
        new_user = User(name=name, email=email, password_hash=hashed_pwd)
        db.session.add(new_user)
        db.session.commit()
        
        # Initialize Default Categories for user
        for cat in DEFAULT_CATEGORIES:
            db.session.add(Category(user_id=new_user.id, category_name=cat, monthly_budget=5000.00))
        db.session.commit()
        
        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        return redirect(url_for('setup_budgets'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/setup-budgets', methods=['GET', 'POST'])
@login_required
def setup_budgets():
    user_id = session['user_id']
    if request.method == 'POST':
        for cat_name in DEFAULT_CATEGORIES:
            budget_val = request.form.get(f'budget_{cat_name}', 0.0)
            category = Category.query.filter_by(user_id=user_id, category_name=cat_name).first()
            if category:
                category.monthly_budget = float(budget_val)
        db.session.commit()
        return redirect(url_for('dashboard'))
        
    categories = Category.query.filter_by(user_id=user_id).all()
    return render_template('setup_budgets.html', categories=categories)

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    categories = Category.query.filter_by(user_id=user_id).all()
    recent_txns = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.transaction_date.desc()).limit(10).all()
    
    total_budget = sum(float(c.monthly_budget) for c in categories)
    total_spent = sum(float(c.current_spent) for c in categories)
    total_savings = max(0.0, total_budget - total_spent)
    
    return render_template('dashboard.html', 
                           categories=categories, 
                           transactions=recent_txns, 
                           total_budget=total_budget, 
                           total_spent=total_spent, 
                           total_savings=total_savings)

@app.route('/add-expense', methods=['POST'])
@login_required
def add_expense():
    data = request.get_json() or {}
    merchant = data.get('merchant_name', '').strip()
    amount = float(data.get('amount', 0))
    payment_method = data.get('payment_method', 'UPI')
    
    if not merchant or amount <= 0:
        return jsonify({'success': False, 'message': 'Invalid expense data'}), 400
        
    user_id = session['user_id']
    ai_cat_name = ai_categorize_merchant(merchant)
    
    category = Category.query.filter_by(user_id=user_id, category_name=ai_cat_name).first()
    if not category:
        category = Category.query.filter_by(user_id=user_id, category_name="Others").first()
        ai_cat_name = "Others"
        
    # Save Transaction
    txn = Transaction(
        user_id=user_id,
        category_id=category.id,
        merchant_name=merchant,
        amount=amount,
        payment_method=payment_method,
        ai_category=ai_cat_name
    )
    
    # Update Category Spent
    category.current_spent = float(category.current_spent) + amount
    db.session.add(txn)
    db.session.commit()
    
    # Threshold Evaluation & Real-Time Alert Engine
    spent = float(category.current_spent)
    budget = float(category.monthly_budget)
    threshold = (spent / budget * 100) if budget > 0 else 0
    
    alert = None
    if threshold >= 100:
        alert = {
            'type': 'critical',
            'message': f'Alert: {category.category_name} budget exceeded by ₹{spent - budget:.2f}!'
        }
    elif threshold >= 80:
        alert = {
            'type': 'warning',
            'message': f'Warning: You have reached {threshold:.1f}% of your {category.category_name} budget!'
        }
        
    return jsonify({
        'success': True,
        'message': 'Transaction recorded successfully',
        'ai_category': ai_cat_name,
        'alert': alert,
        'transaction': {
            'id': txn.id,
            'merchant': txn.merchant_name,
            'amount': float(txn.amount),
            'method': txn.payment_method,
            'category': txn.ai_category,
            'date': txn.transaction_date.strftime('%Y-%m-%d %H:%M')
        }
    })

@app.route('/predict-budget', methods=['GET'])
@login_required
def predict_budget():
    user_id = session['user_id']
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    categories = Category.query.filter_by(user_id=user_id).all()
    predictions = []
    
    for cat in categories:
        txns = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.category_id == cat.id,
            Transaction.transaction_date >= thirty_days_ago
        ).all()
        
        sum_30 = sum(float(t.amount) for t in txns)
        # Moving average project for next month (+10% safety buffer)
        projected = round(sum_30 * 1.10, 2)
        
        predictions.append({
            'category': cat.category_name,
            'current_budget': float(cat.monthly_budget),
            'spent_30d': sum_30,
            'projected_next_month': projected
        })
        
    return jsonify({'success': True, 'predictions': predictions})

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    user_id = session['user_id']
    user_msg = request.json.get('message', '')
    
    categories = Category.query.filter_by(user_id=user_id).all()
    total_budget = sum(float(c.monthly_budget) for c in categories)
    total_spent = sum(float(c.current_spent) for c in categories)
    remaining = total_budget - total_spent
    
    top_categories = sorted(categories, key=lambda x: float(x.current_spent), reverse=True)[:3]
    top_cats_str = ", ".join([f"{c.category_name}: ₹{c.current_spent}" for c in top_categories])
    
    # Financial context injection
    context_prompt = f"""
    You are FinSight AI, a senior expert personal financial advisor.
    
    User Context Summary:
    - Monthly Total Budget: ₹{total_budget:.2f}
    - Total Spent so far: ₹{total_spent:.2f}
    - Remaining Budget: ₹{remaining:.2f}
    - Top Spending Categories: {top_cats_str}
    
    User Query: "{user_msg}"
    
    Instructions:
    Provide actionable, empathetic, concise advice. Keep points structured with bullet points.
    """
    try:
        response = gemini_model.generate_content(context_prompt)
        return jsonify({'success': True, 'reply': response.text})
    except Exception as e:
        return jsonify({'success': False, 'reply': f'Error contacting AI Assistant: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)