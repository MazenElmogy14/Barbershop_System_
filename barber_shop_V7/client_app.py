from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text # NEEDED FOR DATABASE UPDATES
from datetime import datetime, date
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'client-booking-secret'

# Set DB path correctly to point to the main instance database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'barberV7.db')

db = SQLAlchemy(app)

# Map existing tables
class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class ClientRequest(db.Model):
    __tablename__ = 'client_requests'
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    client_phone = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    
    appointment_time = db.Column(db.Time, nullable=True)
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    
    # NEW COLUMNS FOR DEVICE IP TRACKING
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.Date, default=date.today)

    barber = db.relationship('Barber')
    service = db.relationship('Service')

with app.app_context():
    db.create_all()
    
    # Safely add new columns to your existing database without deleting data
    try:
        db.session.execute(text("ALTER TABLE client_requests ADD COLUMN ip_address VARCHAR(45)"))
        db.session.commit()
    except Exception:
        db.session.rollback() # Column already exists
        
    try:
        db.session.execute(text("ALTER TABLE client_requests ADD COLUMN created_at DATE"))
        db.session.commit()
    except Exception:
        db.session.rollback() # Column already exists


@app.route('/', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        # 1. GET THE DEVICE IP ADDRESS
        client_ip = request.remote_addr
        today = date.today()
        
        # 2. CHECK IF THIS IP ALREADY BOOKED TODAY
        existing_booking = ClientRequest.query.filter_by(ip_address=client_ip, created_at=today).first()
        
        if existing_booking:
            flash('⚠️ You have already submitted a booking request today from this device. Please wait until tomorrow or contact the shop directly.', 'danger')
            return redirect(url_for('book'))

        # If they haven't booked today, proceed as normal
        name = request.form.get('name')
        phone = request.form.get('phone')
        service_id = request.form.get('service_id')
        date_str = request.form.get('preferred_date')

        try:
            pref_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            new_req = ClientRequest(
                client_name=name,
                client_phone=phone,
                service_id=int(service_id),
                preferred_date=pref_date,
                ip_address=client_ip,  # SAVE THE IP
                created_at=today       # SAVE THE DATE
            )
            db.session.add(new_req)
            db.session.commit()
            flash('Your booking request has been sent! Our staff will contact you shortly with your exact time and barber.', 'success')
            return redirect(url_for('book'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')

    # Pulling all services exactly as Cashier does
    services = Service.query.all()
    
    return render_template('book.html', services=services)

if __name__ == '__main__':
    app.run(debug=True, port=5001, host="0.0.0.0")