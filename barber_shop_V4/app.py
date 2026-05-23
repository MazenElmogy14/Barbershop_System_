from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, date, timedelta, time
from sqlalchemy import func
import json
from flask import make_response
from weasyprint import HTML
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'barber-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///barberV3.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)

class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    commission_type = db.Column(db.String(20), default='percentage') # 'percentage' or 'fixed'
    commission_value = db.Column(db.Float, default=0.0) # 50 means 50% or $50
    total_paid = db.Column(db.Float, default=0.0)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # ضفنا index=True هنا عشان يسرع البحث جداً
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True) 
    points = db.Column(db.Integer, default=0)
    transactions = db.relationship('Transaction', backref='client', lazy=True)



class TransactionService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True) # Can be null if service is deleted
    
    # Financial Snapshots (Never changes even if admin edits the main Service)
    service_name = db.Column(db.String(100), nullable=False)
    price_charged = db.Column(db.Float, nullable=False)



class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    
    # REMOVED the old String column: services = db.Column(db.String(200)) 
    
    total_price = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    barber_cut = db.Column(db.Float, default=0.0) 
    barber = db.relationship('Barber', backref='transactions')
    payment_method = db.Column(db.String(20), default='Cash')
    discount = db.Column(db.Float, default=0.0)

    # ADDED: Link to the junction table
    services_list = db.relationship('TransactionService', backref='transaction', lazy=True, cascade="all, delete-orphan")

    # ADDED: This property fakes the old string column so your HTML templates don't break!
    @property
    def services(self):
        return ", ".join([ts.service_name for ts in self.services_list])

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    # Optional but recommended: Add a soft-delete flag for the future
    is_active = db.Column(db.Boolean, default=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if user:
            login_user(user)
            return redirect(url_for('owner' if user.role == 'owner' else 'cashier'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))



POINTS_CONFIG = {
    'MODE': 'PER_UNIT',      # اختر 'PER_UNIT' للحساب بالجنيه/الدولار، أو 'PER_TX' لعدد ثابت للفاتورة
    'POINTS_PER_TX': 15
}


@app.route('/cashier', methods=['GET', 'POST'])
@login_required
def cashier():
    selected_services = []
    services = Service.query.all()
    barbers = Barber.query.all()

    if request.method == 'POST':
        client_type = request.form.get('client_type')
        phone = request.form.get('phone')
        name = request.form.get('name')
        barber_id = request.form.get('barber_id')
        service_ids = request.form.getlist('services')
        use_points = request.form.get('use_points')
        payment_method = request.form.get('payment_method', 'Cash')
        
        # جلب النسبة المئوية من الواجهة (الافتراضي 0)
        discount_percent = float(request.form.get('discount_percent', 0.0) or 0.0)

        client = Client.query.filter_by(phone=phone).first()

        # معالجة العميل
        if client_type == 'new':
            if not client:
                client = Client(name=name, phone=phone, points=0)
                db.session.add(client)
                db.session.commit()
        else:
            if not client:
                flash("Client not found! Please register as New.", "danger")
                return redirect(url_for('cashier'))

        # حساب الخدمات
        selected_services = Service.query.filter(Service.id.in_(service_ids)).all()
        total_price = sum(s.price for s in selected_services)
        
        # حساب قيمة الخصم بناءً على النسبة المئوية
        manual_discount_amount = total_price * (discount_percent / 100.0)
        
        # حساب خصم نقاط الولاء (لو العميل اختار يستخدمها)
        points_discount = 5.0 if (use_points and client.points >= 100) else 0.0
        
        # إجمالي الخصم
        total_discount = points_discount + manual_discount_amount
        
        # خصم النقاط من رصيد العميل لو استخدمها
        if points_discount > 0:
            client.points -= 100

        # الإجمالي النهائي بعد الخصم
        final_total = max(0.0, total_price - total_discount)
        
        # حساب عمولة الحلاق
        barber = Barber.query.get(barber_id)
        barber_cut = final_total * (barber.commission_value / 100.0) if barber else 0

        # تسجيل الفاتورة
        new_tx = Transaction(
            name=client.name,
            phone=client.phone,
            # Notice we removed the "services" string mapping here
            total_price=final_total,
            discount=total_discount,  
            barber_id=barber.id if barber else None,
            barber_cut=barber_cut,
            client_id=client.id,
            payment_method=payment_method
        )
        db.session.add(new_tx)
        

        for service in selected_services:
            tx_service = TransactionService(
                transaction=new_tx,        # Automatically links to new_tx ID
                service_id=service.id,
                service_name=service.name, # Snapshot the name right now
                price_charged=service.price # Snapshot the price right now
            )
            db.session.add(tx_service)
        # إضافة النقاط الجديدة لرصيد العميل
        if POINTS_CONFIG['MODE'] == 'PER_UNIT':
            client.points += int(final_total)
        else:
            client.points += POINTS_CONFIG['POINTS_PER_TX']
            
        db.session.commit()
        return redirect(url_for('receipt', tx_id=new_tx.id))

    return render_template('cashier.html', services=services, barbers=barbers)



@app.route('/clients_history')
@login_required
def clients_history():
    # جلب جميع العملاء من قاعدة البيانات
    clients = Client.query.order_by(Client.id.desc()).all()
    return render_template('clients_history.html', clients=clients)



@app.route('/api/client/<phone>')
@login_required
def get_client(phone):
    client = Client.query.filter_by(phone=phone).first()
    if client:
        # بنجيب آخر 5 عمليات للعميل
        transactions = Transaction.query.filter_by(client_id=client.id).order_by(Transaction.timestamp.desc()).limit(5).all()
        history = [{"date": t.timestamp.strftime('%Y-%m-%d'), "services": t.services, "total": t.total_price} for t in transactions]
        
        # التأكد من إرسال الـ points في الـ JSON
        return jsonify({
            "found": True, 
            "name": client.name, 
            "points": client.points, # <--- تأكد من هذا السطر
            "history": history
        })
    return jsonify({"found": False})

@app.route('/clients')
@login_required
def clients():
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_transactions = Transaction.query.filter(Transaction.timestamp >= thirty_days_ago).order_by(Transaction.timestamp.desc()).all()
    return render_template('clients.html', transactions=recent_transactions)

@app.route('/receipt/<int:tx_id>')
@login_required
def receipt(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    return render_template('receipt.html', tx=tx)

@app.route('/owner')
@login_required
def owner():
    if current_user.role != 'owner': return "Access Denied"

    time_range = request.args.get('range', 'today')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    today = date.today()
    start_date = today
    end_date = today
    date_label = "Today's"

    if time_range == '7days':
        start_date = today - timedelta(days=7)
        date_label = "Last 7 Days"
    elif time_range == 'monthly':
        start_date = today.replace(day=1)
        date_label = "This Month's"
    elif time_range == 'yearly':
        start_date = today.replace(month=1, day=1)
        date_label = "This Year's"
    elif time_range == 'custom' and start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        date_label = f"From {start_date_str} to {end_date_str}"
    else:
        time_range = 'today' 

    # 🔥 THE FIX: Create strict Midnight to 11:59 PM bounds
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    # Bulletproof filtering without using func.date()
    transactions = Transaction.query.filter(
        Transaction.timestamp >= start_dt,
        Transaction.timestamp <= end_dt
    ).all()
    
    total_revenue = sum(t.total_price for t in transactions)
    total_commissions = sum(t.barber_cut for t in transactions)
    
    expenses = Expense.query.filter(
        Expense.date >= start_dt,
        Expense.date <= end_dt
    ).all()
    
    total_expenses = sum(e.amount for e in expenses)
    net_profit = (total_revenue - total_commissions) - total_expenses

    barbers = Barber.query.all()
    barber_names = [b.name for b in barbers]
    barber_values = [sum(t.total_price for t in transactions if t.barber_id == b.id) for b in barbers]

    return render_template(
        'owner.html',
        transactions=transactions,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=net_profit,
        barber_names=barber_names,
        barber_values=barber_values,
        date_label=date_label,
        current_range=time_range,
        total_commissions=total_commissions,
        expenses_list=expenses
    )




@app.route('/export_pdf')
@login_required
def export_pdf():
    if current_user.role != 'owner': return "Access Denied"

    time_range = request.args.get('range', 'today')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')

    today = date.today()
    start_date = today
    end_date = today
    date_label = "Today's"

    if time_range == '7days':
        start_date = today - timedelta(days=7)
        date_label = "Last 7 Days"
    elif time_range == 'monthly':
        start_date = today.replace(day=1)
        date_label = "This Month's"
    elif time_range == 'yearly':
        start_date = today.replace(month=1, day=1)
        date_label = "This Year's"
    elif time_range == 'custom' and start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        date_label = f"From {start_date_str} to {end_date_str}"

    # 🔥 THE FIX: Create strict Midnight to 11:59 PM bounds
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    transactions = Transaction.query.filter(
        Transaction.timestamp >= start_dt,
        Transaction.timestamp <= end_dt
    ).all()
    
    total_revenue = sum(t.total_price for t in transactions)
    total_commissions = sum(t.barber_cut for t in transactions)
    
    expenses = Expense.query.filter(
        Expense.date >= start_dt,
        Expense.date <= end_dt
    ).all()
    
    total_expenses = sum(e.amount for e in expenses)
    net_profit = (total_revenue - total_commissions) - total_expenses

    html_content = render_template(
        'pdf_report.html',
        transactions=transactions,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=net_profit,
        total_commissions=total_commissions,
        expenses_list=expenses,
        date_label=date_label,
        today_date=today.strftime('%Y-%m-%d')
    )

    pdf = HTML(string=html_content).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    safe_filename = date_label.replace(" ", "_").replace("/", "-")
    response.headers['Content-Disposition'] = f'attachment; filename=Elite_Report_{safe_filename}.pdf'
    
    return response


@app.route('/manage_barbers', methods=['GET', 'POST'])
@login_required
def manage_barbers():
    if current_user.role != 'owner': return "Access Denied"
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_b = Barber(
                name=request.form['name'],
                commission_type=request.form['commission_type'],
                commission_value=float(request.form['commission_value'])
            )
            db.session.add(new_b)
        elif action == 'pay':
            b_id = request.form['barber_id']
            amount = float(request.form['amount'])
            barber = Barber.query.get(b_id)
            if barber:
                barber.total_paid += amount
        db.session.commit()
        return redirect(url_for('manage_barbers'))

    barbers = Barber.query.all()
    stats = []
    for b in barbers:
        total_earned = sum(t.barber_cut for t in b.transactions) # His money (Barber's cut)
        balance = total_earned - b.total_paid                    # What you still owe him
        
        # --- NEW CALCULATIONS ---
        total_shop_revenue = sum(t.total_price for t in b.transactions) # Total money he brought to the shop
        total_transactions = len(b.transactions)                        # How many clients he served
        
        stats.append({
            'barber': b, 
            'total_earned': total_earned, 
            'balance': balance,
            'shop_revenue': total_shop_revenue, # Added to dictionary
            'clients_served': total_transactions # Added to dictionary
        })
        
    return render_template('manage_barbers.html', stats=stats)



@app.route('/edit_barber/<int:id>', methods=['POST'])
@login_required
def edit_barber(id):
    if current_user.role != 'owner': return "Access Denied"
    barber = Barber.query.get_or_404(id)
    barber.name = request.form['name']
    barber.commission_type = request.form['commission_type']
    barber.commission_value = float(request.form['commission_value'])
    db.session.commit()
    return redirect(url_for('manage_barbers'))

@app.route('/delete_barber/<int:id>', methods=['POST'])
@login_required
def delete_barber(id):
    if current_user.role != 'owner': return "Access Denied"
    barber = Barber.query.get_or_404(id)
    db.session.delete(barber)
    db.session.commit()
    return redirect(url_for('manage_barbers'))

@app.route('/manage_services', methods=['GET', 'POST'])
@login_required
def manage_services():
    if current_user.role != 'owner': return "Access Denied"
    if request.method == 'POST':
        new_service = Service(name=request.form['name'], price=float(request.form['price']))
        db.session.add(new_service)
        db.session.commit()
        return redirect(url_for('manage_services'))
    services = Service.query.all()
    return render_template('manage_services.html', services=services)

@app.route('/edit_service/<int:id>', methods=['POST'])
@login_required
def edit_service(id):
    if current_user.role != 'owner': return "Access Denied"
    service = Service.query.get_or_404(id)
    service.name = request.form['name']
    service.price = float(request.form['price'])
    db.session.commit()
    return redirect(url_for('manage_services'))

@app.route('/delete_service/<int:id>', methods=['POST'])
@login_required
def delete_service(id):
    if current_user.role != 'owner': return "Access Denied"
    service = Service.query.get_or_404(id)
    db.session.delete(service)
    db.session.commit()
    return redirect(url_for('manage_services'))

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'owner': return "Access Denied"
    if request.method == 'POST':
        new_user = User(username=request.form['username'], password=request.form['password'], role=request.form['role'])
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('manage_users'))
    users = User.query.all()
    return render_template('manage_users.html', users=users)



@app.route('/manage_expenses', methods=['GET', 'POST'])
@login_required
def manage_expenses():
    if current_user.role != 'owner': return "Access Denied"
    
    if request.method == 'POST':
        new_expense = Expense(
            description=request.form['description'],
            amount=float(request.form['amount'])
        )
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for('manage_expenses'))
        
    expenses = Expense.query.order_by(Expense.date.desc()).all()
    total_expenses = sum(e.amount for e in expenses)
    return render_template('manage_expenses.html', expenses=expenses, total=total_expenses)




@app.route('/set_lang/<lang>')
def set_lang(lang):
    """Route to switch language and save to session"""
    session['lang'] = lang
    # Redirect back to the page the user was just on
    return redirect(request.referrer or url_for('login'))

@app.context_processor
def inject_translations():
    """This function makes the translation dictionary available to ALL HTML templates automatically"""
    lang = session.get('lang', 'en') # Default to English
    translations = {}
    
    if lang != 'en':
        try:
            with open('translations.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                translations = data.get(lang, {})
        except FileNotFoundError:
            pass # If file is missing, just fallback to English
            
    # Create a helper function to translate keys
    def t(key, default_english):
        return translations.get(key, default_english)
        
    # Variables passed here are available in all templates using {{ current_lang }} or {{ t('key', 'Default') }}
    return dict(t=t, current_lang=lang)



with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123', role='owner'))
        db.session.add(User(username='staff', password='123', role='cashier'))
        db.session.commit()
    if not Service.query.first():
        db.session.add(Service(name="Haircut", price=50.0))
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)