from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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

    barber = db.relationship('Barber')
    service = db.relationship('Service')

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
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
                preferred_date=pref_date
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