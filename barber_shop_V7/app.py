from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, date, timedelta, time
from sqlalchemy import func
import json
from flask import make_response
from weasyprint import HTML
import os
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'talentx-saas-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///barber_saas.db'

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==========================================
# SAAS MULTI-TENANT MODELS
# ==========================================
class Salon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=True) 
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    linked_barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    
    salon = db.relationship('Salon', backref='users')
    barber = db.relationship('Barber', backref='user_account')

class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    commission_type = db.Column(db.String(20), default='percentage')
    commission_value = db.Column(db.Float, default=0.0)
    total_paid = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False) 
    points = db.Column(db.Integer, default=0)
    transactions = db.relationship('Transaction', backref='client', lazy=True)

class TransactionService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    service_name = db.Column(db.String(100), nullable=False)
    price_charged = db.Column(db.Float, nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    total_price = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    barber_cut = db.Column(db.Float, default=0.0) 
    barber = db.relationship('Barber', backref='transactions')
    payment_method = db.Column(db.String(20), default='Cash')
    discount = db.Column(db.Float, default=0.0)
    photo_filename = db.Column(db.String(255), nullable=True)
    products_list = db.relationship('TransactionProduct', backref='transaction', lazy=True, cascade="all, delete-orphan")
    services_list = db.relationship('TransactionService', backref='transaction', lazy=True, cascade="all, delete-orphan")

    @property
    def services(self):
        return ", ".join([ts.service_name for ts in self.services_list])

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    cost_price = db.Column(db.Float, nullable=False, default=0.0) 
    selling_price = db.Column(db.Float, nullable=False, default=0.0) 
    stock = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5) 
    is_active = db.Column(db.Boolean, default=True)

class TransactionProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True) 
    product_name = db.Column(db.String(100), nullable=False)
    price_charged = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

class ClientRequest(db.Model):
    __tablename__ = 'client_requests'
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    client_phone = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=True)
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.Date, default=date.today)

    barber = db.relationship('Barber')
    service = db.relationship('Service')

class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salon_id = db.Column(db.Integer, db.ForeignKey('salon.id'), nullable=False)
    feature_name = db.Column(db.String(50), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HELPER TO CHECK IF FEATURE IS ENABLED ---
def is_feature_enabled(salon_id, feature_name):
    setting = SystemSetting.query.filter_by(salon_id=salon_id, feature_name=feature_name).first()
    return setting.is_enabled if setting else True


# ==========================================
# PUBLIC SAAS ROUTES (BOOKING PORTAL)
# ==========================================
@app.route('/book/<salon_slug>', methods=['GET', 'POST'])
def book(salon_slug):
    salon = Salon.query.filter_by(slug=salon_slug.lower(), is_active=True).first_or_404()
    
    if not is_feature_enabled(salon.id, 'online_booking'):
        return "This salon has disabled online booking.", 403

    if request.method == 'POST':
        client_ip = request.remote_addr
        today = date.today()
        
        existing_booking = ClientRequest.query.filter_by(salon_id=salon.id, ip_address=client_ip, created_at=today).first()
        if existing_booking:
            flash('⚠️ You have already submitted a booking request today from this device. Please wait until tomorrow.', 'danger')
            return redirect(url_for('book', salon_slug=salon.slug))

        name = request.form.get('name')
        phone = request.form.get('phone')
        service_id = request.form.get('service_id')
        date_str = request.form.get('preferred_date')

        try:
            pref_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            new_req = ClientRequest(
                salon_id=salon.id,
                client_name=name,
                client_phone=phone,
                service_id=int(service_id),
                preferred_date=pref_date,
                ip_address=client_ip,
                created_at=today
            )
            db.session.add(new_req)
            db.session.commit()
            flash('Your booking request has been sent! Our staff will contact you shortly to confirm.', 'success')
            return redirect(url_for('book', salon_slug=salon.slug))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')

    services = Service.query.filter_by(salon_id=salon.id, is_active=True).all()
    return render_template('book.html', salon=salon, services=services)


# ==========================================
# INTERNAL SYSTEM ROUTES
# ==========================================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if user:
            if user.salon_id:
                salon = Salon.query.get(user.salon_id)
                if not salon.is_active:
                    flash('Your salon account is currently suspended. Contact support.')
                    return render_template('login.html')

            login_user(user)
            if user.role == 'superadmin':
                return redirect(url_for('superadmin_portal'))
            elif user.role == 'owner':
                return redirect(url_for('owner'))
            elif user.role == 'barber':
                return redirect(url_for('barber_dashboard'))
            else:
                return redirect(url_for('cashier'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/cashier', methods=['GET', 'POST'])
@login_required
def cashier():
    sid = current_user.salon_id
    if not is_feature_enabled(sid, 'pos'): return "Access Denied: POS module is disabled.", 403

    services = Service.query.filter_by(salon_id=sid, is_active=True).all()
    barbers = Barber.query.filter_by(salon_id=sid).all()
    products = Product.query.filter_by(salon_id=sid, is_active=True).all()

    if request.method == 'POST':
        client_type = request.form.get('client_type')
        phone = request.form.get('phone')
        name = request.form.get('name')
        barber_id = request.form.get('barber_id')
        service_ids = request.form.getlist('services')
        product_ids = request.form.getlist('products') 
        use_points = request.form.get('use_points')
        payment_method = request.form.get('payment_method', 'Cash')
        discount_percent = float(request.form.get('discount_percent', 0.0) or 0.0)

        client = Client.query.filter_by(salon_id=sid, phone=phone).first()

        if client_type == 'new':
            if not client:
                client = Client(salon_id=sid, name=name, phone=phone, points=0)
                db.session.add(client)
                db.session.commit()
        else:
            if not client:
                flash("Client not found! Please register as New.", "danger")
                return redirect(url_for('cashier'))

        selected_services = Service.query.filter(Service.id.in_(service_ids), Service.salon_id==sid).all()
        services_total = sum(s.price for s in selected_services)
        
        selected_products = Product.query.filter(Product.id.in_(product_ids), Product.salon_id==sid).all()
        products_total = 0
        
        for p in selected_products:
            if p.stock < 1:
                flash(f"Error: {p.name} is completely out of stock!", "danger")
                return redirect(url_for('cashier'))
            products_total += p.selling_price

        subtotal = services_total + products_total
        manual_discount_amount = subtotal * (discount_percent / 100.0)
        points_discount = 5.0 if (use_points and client.points >= 100) else 0.0
        total_discount = points_discount + manual_discount_amount
        
        if points_discount > 0:
            client.points -= 100

        final_total = max(0.0, subtotal - total_discount)
        barber = Barber.query.filter_by(id=barber_id, salon_id=sid).first()
        services_share = max(0.0, services_total - total_discount)
        
        barber_cut = 0.0
        if barber:
            if barber.commission_type == 'fixed':
                barber_cut = barber.commission_value
            else:
                barber_cut = services_share * (barber.commission_value / 100.0)

        try:
            new_tx = Transaction(
                salon_id=sid,
                name=client.name,
                phone=client.phone,
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
                    transaction=new_tx,
                    service_id=service.id,
                    service_name=service.name,
                    price_charged=service.price
                )
                db.session.add(tx_service)

            for product in selected_products:
                tx_product = TransactionProduct(
                    transaction=new_tx,
                    product_id=product.id,
                    product_name=product.name,
                    price_charged=product.selling_price,
                    quantity=1
                )
                db.session.add(tx_product)
                product.stock -= 1

            if is_feature_enabled(sid, 'loyalty_points'):
                client.points += 15
                
            db.session.commit()
            return redirect(url_for('receipt', tx_id=new_tx.id))

        except Exception as e:
            db.session.rollback()
            flash("An unexpected error occurred during checkout.", "danger")
            return redirect(url_for('cashier'))

    return render_template('cashier.html', services=services, barbers=barbers, products=products)

@app.route('/clients_history')
@login_required
def clients_history():
    clients = Client.query.filter_by(salon_id=current_user.salon_id).order_by(Client.id.desc()).all()
    return render_template('clients_history.html', clients=clients)

@app.route('/api/client/<phone>')
@login_required
def get_client(phone):
    client = Client.query.filter_by(salon_id=current_user.salon_id, phone=phone).first()
    if client:
        transactions = Transaction.query.filter_by(client_id=client.id, salon_id=current_user.salon_id).order_by(Transaction.timestamp.desc()).limit(5).all()
        history = [{"date": t.timestamp.strftime('%Y-%m-%d'), "services": t.services, "total": t.total_price} for t in transactions]
        return jsonify({"found": True, "name": client.name, "points": client.points, "history": history})
    return jsonify({"found": False})

@app.route('/api/client_history_photos/<int:client_id>')
@login_required
def get_client_history_photos(client_id):
    client = Client.query.filter_by(id=client_id, salon_id=current_user.salon_id).first_or_404()
    transactions = Transaction.query.filter(
        Transaction.client_id == client.id, 
        Transaction.photo_filename != None
    ).order_by(Transaction.timestamp.desc()).all()
    
    history = []
    for t in transactions:
        history.append({
            "date": t.timestamp.strftime('%Y-%m-%d'), 
            "services": t.services, 
            "photo_url": url_for('static', filename='uploads/' + t.photo_filename)
        })
    return jsonify({"name": client.name, "history": history})

@app.route('/clients')
@login_required
def clients():
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_transactions = Transaction.query.filter(Transaction.salon_id==current_user.salon_id, Transaction.timestamp >= thirty_days_ago).order_by(Transaction.timestamp.desc()).all()
    return render_template('clients.html', transactions=recent_transactions)

@app.route('/receipt/<int:tx_id>')
@login_required
def receipt(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, salon_id=current_user.salon_id).first_or_404()
    return render_template('receipt.html', tx=tx)

@app.route('/barber_dashboard')
@login_required
def barber_dashboard():
    if current_user.role != 'barber': return "Access Denied"
    
    if not current_user.linked_barber_id:
        flash("⚠️ Warning: Your account is not linked to a Barber profile.", "danger")
        return render_template('barber_dashboard.html', transactions=[], approved_requests=[])
    
    today = date.today()
    
    transactions = Transaction.query.filter(
        Transaction.salon_id == current_user.salon_id,
        Transaction.barber_id == current_user.linked_barber_id,
        Transaction.photo_filename.is_(None)
    ).order_by(Transaction.timestamp.desc()).all()
    
    approved_requests = ClientRequest.query.filter(
        ClientRequest.salon_id == current_user.salon_id,
        ClientRequest.barber_id == current_user.linked_barber_id,
        ClientRequest.status == 'Approved',
        ClientRequest.preferred_date >= today
    ).order_by(ClientRequest.preferred_date, ClientRequest.appointment_time).all()
    
    return render_template('barber_dashboard.html', 
                           transactions=transactions, 
                           approved_requests=approved_requests)

@app.route('/upload_cut_photo/<int:tx_id>', methods=['POST'])
@login_required
def upload_cut_photo(tx_id):
    if current_user.role not in ['barber', 'owner']: return "Access Denied"
    tx = Transaction.query.filter_by(id=tx_id, salon_id=current_user.salon_id).first_or_404()
    
    if 'photo' not in request.files:
        flash('No file part')
        return redirect(request.referrer)
        
    file = request.files['photo']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.referrer)
        
    if file:
        filename = secure_filename(f"cut_tx{tx.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        tx.photo_filename = filename
        db.session.commit()
    
    return redirect(request.referrer)

@app.route('/owner')
@login_required
def owner():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id

    if 'range' in request.args:
        session['dashboard_range'] = request.args.get('range')
        session['dashboard_start'] = request.args.get('start_date', '')
        session['dashboard_end'] = request.args.get('end_date', '')

    time_range = session.get('dashboard_range', 'today')
    start_date_str = session.get('dashboard_start', '')
    end_date_str = session.get('dashboard_end', '')

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

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    transactions = Transaction.query.filter(
        Transaction.salon_id == sid,
        Transaction.timestamp >= start_dt,
        Transaction.timestamp <= end_dt
    ).all()
    
    total_revenue = sum(t.total_price for t in transactions)
    total_commissions = sum(t.barber_cut for t in transactions)
    
    expenses = Expense.query.filter(
        Expense.salon_id == sid,
        Expense.date >= start_dt,
        Expense.date <= end_dt
    ).all()
    
    total_expenses = sum(e.amount for e in expenses)
    net_profit = (total_revenue - total_commissions) - total_expenses

    barbers = Barber.query.filter_by(salon_id=sid).all()
    barber_names = [b.name for b in barbers]
    barber_values = [sum(t.total_price for t in transactions if t.barber_id == b.id) for b in barbers]

    salon_obj = Salon.query.get(sid)
    booking_url = url_for('book', salon_slug=salon_obj.slug, _external=True)

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
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        total_commissions=total_commissions,
        expenses_list=expenses,
        booking_url=booking_url
    )

@app.route('/export_pdf')
@login_required
def export_pdf():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id
    if not is_feature_enabled(sid, 'pdf_report'): return "Access Denied: PDF Export is disabled.", 403

    time_range = request.args.get('range') or session.get('dashboard_range', 'today')
    start_date_str = request.args.get('start_date') or session.get('dashboard_start', '')
    end_date_str = request.args.get('end_date') or session.get('dashboard_end', '')

    today = date.today()
    start_date = today
    end_date = today
    date_label = "Today's"

    if time_range == '7days':
        start_date = today - timedelta(days=7)
    elif time_range == 'monthly':
        start_date = today.replace(day=1)
    elif time_range == 'yearly':
        start_date = today.replace(month=1, day=1)
    elif time_range == 'custom' and start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    transactions = Transaction.query.filter(
        Transaction.salon_id == sid,
        Transaction.timestamp >= start_dt,
        Transaction.timestamp <= end_dt
    ).all()
    
    total_revenue = sum(t.total_price for t in transactions)
    total_commissions = sum(t.barber_cut for t in transactions)
    
    expenses = Expense.query.filter(
        Expense.salon_id == sid,
        Expense.date >= start_dt,
        Expense.date <= end_dt
    ).all()
    
    total_expenses = sum(e.amount for e in expenses)
    net_profit = (total_revenue - total_commissions) - total_expenses

    all_barbers = Barber.query.filter_by(salon_id=sid).all()
    barber_stats = []
    for b in all_barbers:
        b_txs = [t for t in transactions if t.barber_id == b.id]
        barber_stats.append({
            'name': b.name,
            'clients': len(b_txs),
            'revenue': sum(t.total_price for t in b_txs),
            'cut': sum(t.barber_cut for t in b_txs),
            'commission_type': b.commission_type,
            'commission_value': b.commission_value
        })
        
    inventory = Product.query.filter_by(salon_id=sid, is_active=True).all()
    services = Service.query.filter_by(salon_id=sid, is_active=True).all()
    system_users = User.query.filter_by(salon_id=sid).all()
    total_clients = Client.query.filter_by(salon_id=sid).count()

    html_content = render_template(
        'pdf_report.html',
        transactions=transactions,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=net_profit,
        total_commissions=total_commissions,
        expenses_list=expenses,
        date_label=date_label,
        today_date=today.strftime('%Y-%m-%d'),
        barber_stats=barber_stats,
        inventory=inventory,
        services=services,
        system_users=system_users,
        total_clients=total_clients
    )

    pdf = HTML(string=html_content).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    safe_filename = date_label.replace(" ", "_").replace("/", "-")
    response.headers['Content-Disposition'] = f'attachment; filename=Elite_Report_{safe_filename}.pdf'
    return response

@app.route('/manage_products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id
    if not is_feature_enabled(sid, 'inventory'): return "Access Denied: Inventory module is disabled.", 403

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_prod = Product(
                salon_id=sid,
                name=request.form['name'],
                cost_price=float(request.form['cost_price']),
                selling_price=float(request.form['selling_price']),
                stock=int(request.form['stock']),
                low_stock_threshold=int(request.form['low_stock_threshold'])
            )
            db.session.add(new_prod)
        elif action == 'restock':
            p_id = request.form['product_id']
            product = Product.query.filter_by(id=p_id, salon_id=sid).first()
            if product:
                product.stock += int(request.form['quantity'])
        db.session.commit()
        return redirect(url_for('manage_products'))

    all_products = Product.query.filter_by(salon_id=sid, is_active=True).all()
    low_stock_alerts = [p for p in all_products if p.stock <= p.low_stock_threshold]
    return render_template('manage_products.html', products=all_products, alerts=low_stock_alerts)

@app.route('/manage_barbers', methods=['GET', 'POST'])
@login_required
def manage_barbers():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id
    if not is_feature_enabled(sid, 'manage_barbers'): return "Access Denied: Barber management is disabled.", 403

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            new_b = Barber(
                salon_id=sid,
                name=request.form['name'],
                commission_type=request.form['commission_type'],
                commission_value=float(request.form['commission_value'])
            )
            db.session.add(new_b)
        elif action == 'pay':
            b_id = request.form['barber_id']
            barber = Barber.query.filter_by(id=b_id, salon_id=sid).first()
            if barber:
                barber.total_paid += float(request.form['amount'])
        db.session.commit()
        return redirect(url_for('manage_barbers'))

    barbers = Barber.query.filter_by(salon_id=sid).all()
    stats = []
    for b in barbers:
        total_earned = sum(t.barber_cut for t in b.transactions) 
        balance = total_earned - b.total_paid                    
        total_shop_revenue = sum(t.total_price for t in b.transactions) 
        stats.append({
            'barber': b, 
            'total_earned': total_earned, 
            'balance': balance,
            'shop_revenue': total_shop_revenue, 
            'clients_served': len(b.transactions) 
        })
    return render_template('manage_barbers.html', stats=stats)

@app.route('/edit_barber/<int:id>', methods=['POST'])
@login_required
def edit_barber(id):
    if current_user.role != 'owner': return "Access Denied"
    barber = Barber.query.filter_by(id=id, salon_id=current_user.salon_id).first_or_404()
    barber.name = request.form['name']
    barber.commission_type = request.form['commission_type']
    barber.commission_value = float(request.form['commission_value'])
    db.session.commit()
    return redirect(url_for('manage_barbers'))

@app.route('/delete_barber/<int:id>', methods=['POST'])
@login_required
def delete_barber(id):
    if current_user.role != 'owner': return "Access Denied"
    barber = Barber.query.filter_by(id=id, salon_id=current_user.salon_id).first_or_404()
    db.session.delete(barber)
    db.session.commit()
    return redirect(url_for('manage_barbers'))

@app.route('/manage_services', methods=['GET', 'POST'])
@login_required
def manage_services():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id
    if request.method == 'POST':
        new_service = Service(salon_id=sid, name=request.form['name'], price=float(request.form['price']))
        db.session.add(new_service)
        db.session.commit()
        return redirect(url_for('manage_services'))
    services = Service.query.filter_by(salon_id=sid).all()
    return render_template('manage_services.html', services=services)

@app.route('/edit_service/<int:id>', methods=['POST'])
@login_required
def edit_service(id):
    if current_user.role != 'owner': return "Access Denied"
    service = Service.query.filter_by(id=id, salon_id=current_user.salon_id).first_or_404()
    service.name = request.form['name']
    service.price = float(request.form['price'])
    db.session.commit()
    return redirect(url_for('manage_services'))

@app.route('/delete_service/<int:id>', methods=['POST'])
@login_required
def delete_service(id):
    if current_user.role != 'owner': return "Access Denied"
    service = Service.query.filter_by(id=id, salon_id=current_user.salon_id).first_or_404()
    db.session.delete(service)
    db.session.commit()
    return redirect(url_for('manage_services'))

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id
    if not is_feature_enabled(sid, 'manage_users'): return "Access Denied: Account management is disabled.", 403

    if request.method == 'POST':
        role = request.form['role']
        linked_barber_id = request.form.get('linked_barber_id')
        if not linked_barber_id or role != 'barber': 
            linked_barber_id = None

        new_user = User(
            salon_id=sid,
            username=request.form['username'], 
            password=request.form['password'], 
            role=role,
            linked_barber_id=linked_barber_id
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('manage_users'))
    
    users = User.query.filter_by(salon_id=sid).filter(User.role != 'superadmin').all()
    barbers = Barber.query.filter_by(salon_id=sid).all()
    return render_template('manage_users.html', users=users, barbers=barbers)

@app.route('/manage_expenses', methods=['GET', 'POST'])
@login_required
def manage_expenses():
    if current_user.role != 'owner': return "Access Denied"
    sid = current_user.salon_id
    if not is_feature_enabled(sid, 'expenses'): return "Access Denied: Expense module is disabled.", 403

    if request.method == 'POST':
        new_expense = Expense(
            salon_id=sid,
            description=request.form['description'],
            amount=float(request.form['amount'])
        )
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for('manage_expenses'))
    expenses = Expense.query.filter_by(salon_id=sid).order_by(Expense.date.desc()).all()
    total_expenses = sum(e.amount for e in expenses)
    return render_template('manage_expenses.html', expenses=expenses, total=total_expenses)

@app.route('/manage_requests', methods=['GET', 'POST'])
@login_required
def manage_requests():
    if current_user.role not in ['owner', 'cashier']: 
        return "Access Denied"
    
    sid = current_user.salon_id
    if request.method == 'POST':
        req_id = request.form.get('request_id')
        action = request.form.get('action')
        
        client_req = ClientRequest.query.filter_by(id=req_id, salon_id=sid).first()
        
        if action == 'approve':
            barber_id = request.form.get('barber_id')
            time_str = request.form.get('appointment_time')
            
            client_req.barber_id = int(barber_id)
            client_req.appointment_time = datetime.strptime(time_str, '%H:%M').time()
            client_req.status = 'Approved'
            flash(f'Request for {client_req.client_name} Approved!', 'success')
            
        elif action == 'reject':
            client_req.status = 'Rejected'
            flash('Request Rejected.', 'danger')
            
        db.session.commit()
        return redirect(url_for('manage_requests'))
        
    pending_requests = ClientRequest.query.filter_by(salon_id=sid, status='Pending').all()
    approved_requests = ClientRequest.query.filter_by(salon_id=sid, status='Approved').all()
    barbers = Barber.query.filter_by(salon_id=sid).all()
    
    return render_template('manage_requests.html', 
        pending_requests=pending_requests, 
        approved_requests=approved_requests, 
        barbers=barbers)

@app.route('/upload_request_photo/<int:req_id>', methods=['POST'])
@login_required
def upload_request_photo(req_id):
    if current_user.role not in ['barber', 'owner']: return "Access Denied"
    
    client_req = ClientRequest.query.filter_by(id=req_id, salon_id=current_user.salon_id).first_or_404()
    
    if 'photo' not in request.files or request.files['photo'].filename == '':
        flash('No file selected', 'danger')
        return redirect(request.referrer)
        
    file = request.files['photo']
    if file:
        client = Client.query.filter_by(salon_id=current_user.salon_id, phone=client_req.client_phone).first()
        if not client:
            client = Client(salon_id=current_user.salon_id, name=client_req.client_name, phone=client_req.client_phone, points=0)
            db.session.add(client)
            db.session.flush()
            
        service_price = client_req.service.price
        barber = Barber.query.get(client_req.barber_id)
        barber_cut = 0.0
        if barber:
            if barber.commission_type == 'fixed':
                barber_cut = barber.commission_value
            else:
                barber_cut = service_price * (barber.commission_value / 100.0)

        new_tx = Transaction(
            salon_id=current_user.salon_id,
            name=client.name,
            phone=client.phone,
            total_price=service_price,
            barber_id=client_req.barber_id,
            barber_cut=barber_cut,
            client_id=client.id,
            payment_method='Online Booking'
        )
        db.session.add(new_tx)
        db.session.flush() 
        
        tx_service = TransactionService(
            transaction=new_tx,
            service_id=client_req.service_id,
            service_name=client_req.service.name,
            price_charged=service_price
        )
        db.session.add(tx_service)

        filename = secure_filename(f"cut_tx{new_tx.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_tx.photo_filename = filename

        db.session.delete(client_req)
        db.session.commit()
        
        flash('Photo uploaded and online booking completed!', 'success')
        
    return redirect(request.referrer)

# ==========================================
# SAAS MASTER PORTAL (WITH FEATURE TOGGLES)
# ==========================================
AVAILABLE_FEATURES = [
    'online_booking', 'loyalty_points', 'pdf_report', 
    'pos', 'expenses', 'inventory', 'manage_users', 'manage_barbers'
]

@app.route('/superadmin_portal', methods=['GET', 'POST'])
@login_required
def superadmin_portal():
    if current_user.role != 'superadmin': return "Access Denied", 403

    all_salons = Salon.query.all()
    for s in all_salons:
        existing = [stg.feature_name for stg in SystemSetting.query.filter_by(salon_id=s.id).all()]
        for f in AVAILABLE_FEATURES:
            if f not in existing:
                db.session.add(SystemSetting(salon_id=s.id, feature_name=f, is_enabled=True))
    db.session.commit()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'register_salon':
            salon_name = request.form.get('salon_name')
            salon_slug = request.form.get('salon_slug').lower().replace(" ", "-")
            
            if Salon.query.filter_by(slug=salon_slug).first():
                flash("Error: Salon URL slug is already taken. Choose another.", "danger")
            else:
                new_salon = Salon(name=salon_name, slug=salon_slug)
                db.session.add(new_salon)
                db.session.flush() 
                
                owner_username = request.form.get('owner_username')
                owner_password = request.form.get('owner_password')
                db.session.add(User(salon_id=new_salon.id, username=owner_username, password=owner_password, role='owner'))
                
                for f in AVAILABLE_FEATURES:
                    db.session.add(SystemSetting(salon_id=new_salon.id, feature_name=f, is_enabled=True))
                
                db.session.commit()
                flash(f"Successfully registered Salon: {salon_name}", "success")
                
        elif action == 'toggle_status':
            salon_id = request.form.get('salon_id')
            salon = Salon.query.get(salon_id)
            if salon:
                salon.is_active = not salon.is_active
                db.session.commit()
                flash(f"Salon status updated.", "success")
                
        elif action == 'toggle_feature':
            salon_id = request.form.get('salon_id')
            feature_name = request.form.get('feature_name')
            setting = SystemSetting.query.filter_by(salon_id=salon_id, feature_name=feature_name).first()
            if setting:
                setting.is_enabled = not setting.is_enabled
                db.session.commit()
                flash(f"Updated '{feature_name}' for Salon ID {salon_id}", "success")
                
        # --- NEW ACTION: EDIT OWNER ---
        elif action == 'edit_owner':
            salon_id = request.form.get('salon_id')
            new_username = request.form.get('new_username')
            new_password = request.form.get('new_password')
            
            owner_user = User.query.filter_by(salon_id=salon_id, role='owner').first()
            if owner_user:
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user and existing_user.id != owner_user.id:
                    flash("Error: That username is already taken by another account.", "danger")
                else:
                    owner_user.username = new_username
                    # Only change password if the field is not empty
                    if new_password and new_password.strip() != '':
                        owner_user.password = new_password
                    db.session.commit()
                    flash(f"Owner credentials updated successfully for Salon ID {salon_id}!", "success")

        return redirect(url_for('superadmin_portal'))

    salons_data = []
    for s in Salon.query.all():
        owner = User.query.filter_by(salon_id=s.id, role='owner').first()
        settings = SystemSetting.query.filter_by(salon_id=s.id).all()
        salons_data.append({
            'salon': s,
            'owner_username': owner.username if owner else "N/A",
            'settings': settings
        })

    return render_template('superadmin.html', salons_data=salons_data)


# ==========================================
# SYSTEM GLOBALS
# ==========================================
@app.route('/set_lang/<lang>')
def set_lang(lang):
    session['lang'] = lang
    return redirect(request.referrer or url_for('login'))

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    translations = {}
    if lang != 'en':
        try:
            with open('translations.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                translations = data.get(lang, {})
        except FileNotFoundError:
            pass
    def t(key, default_english):
        return translations.get(key, default_english)
    return dict(t=t, current_lang=lang)

@app.context_processor
def inject_global_data():
    lang = session.get('lang', 'en')
    translations = {}
    if lang != 'en':
        try:
            with open('translations.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                translations = data.get(lang, {})
        except FileNotFoundError:
            pass
    def t(key, default_english):
        return translations.get(key, default_english)
        
    low_stock_count = 0
    features = {}
    
    if current_user.is_authenticated and current_user.role != 'superadmin':
        low_stock_count = Product.query.filter(Product.salon_id==current_user.salon_id, Product.is_active == True, Product.stock <= Product.low_stock_threshold).count()
        try:
            settings = SystemSetting.query.filter_by(salon_id=current_user.salon_id).all()
            for s in settings:
                features[s.feature_name] = s.is_enabled
        except:
            pass

    return dict(t=t, current_lang=lang, low_stock_count=low_stock_count, features=features)

with app.app_context():
    db.create_all()
    
    if not User.query.filter_by(username='talentx').first():
        db.session.add(User(username='talentx', password='123', role='superadmin'))
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")