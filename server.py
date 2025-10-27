from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import os
import asyncio
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

app = Flask(__name__)

# Environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'humoyun-tezsot-2025')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Telegram bot tokeni
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7623831722:AAF5IAakgWCKFr7Dc4VifTRiW_zLG1UJAHs')

# Viloyatlar modeli
class Viloyat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Viloyat {self.name}>'

# Ma'muriyat modeli
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

# Ma'lumotlar bazasini yaratish
def create_tables():
    with app.app_context():
        db.create_all()
        if not Admin.query.filter_by(username='admin').first():
            admin_user = Admin(username='admin', password='admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Admin foydalanuvchi yaratildi")

# Flask routelari (oldingi kod bilan bir xil)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return "Login yoki parol xato!"
    return '''
    <form method="post">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Kirish</button>
    </form>
    '''

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    viloyatlar = Viloyat.query.filter_by(is_active=True).all()
    return render_template('admin.html', viloyatlar=viloyatlar)

@app.route('/add_viloyat', methods=['POST'])
def add_viloyat():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    name = request.form['name'].strip()
    if name:
        existing_viloyat = Viloyat.query.filter_by(name=name).first()
        if not existing_viloyat:
            yangi_viloyat = Viloyat(name=name)
            db.session.add(yangi_viloyat)
            db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/delete_viloyat/<int:id>')
def delete_viloyat(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    viloyat = Viloyat.query.get(id)
    if viloyat:
        viloyat.is_active = False
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/api/viloyatlar')
def get_viloyatlar():
    viloyatlar = Viloyat.query.filter_by(is_active=True).all()
    viloyat_list = [{'id': v.id, 'name': v.name} for v in viloyatlar]
    return jsonify(viloyat_list)

@app.route('/')
def home():
    return redirect(url_for('login'))

# Telegram bot funksiyalari
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text(
        f"Salom {user.first_name}! 👋\n"
        f"Viloyatlarni ko'rish uchun /viloyatlar buyrug'ini bering."
    )

async def viloyatlar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import requests
        # Localhostdan viloyatlarni olish
        response = requests.get('http://localhost:5000/api/viloyatlar')
        
        if response.status_code == 200:
            viloyatlar = response.json()
            if viloyatlar:
                message = "🏛️ Viloyatlar ro'yxati:\n\n"
                for index, viloyat in enumerate(viloyatlar, 1):
                    message += f"{index}. {viloyat['name']}\n"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("❌ Hozircha viloyatlar mavjud emas.")
        else:
            await update.message.reply_text("❌ Serverda xatolik yuz berdi.")
    except Exception as e:
        await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

async def run_bot():
    """Botni ishga tushirish"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("viloyatlar", viloyatlar_command))

        print("✅ Telegram bot ishga tushdi!")
        await application.run_polling()
        
    except Exception as e:
        print(f"❌ Botda xatolik: {e}")

def run_bot_sync():
    """Botni sinxron tarzda ishga tushirish"""
    asyncio.run(run_bot())

def start_services():
    """Flask va Botni birga ishga tushirish"""
    # Ma'lumotlar bazasini yaratish
    create_tables()
    
    # Botni background threadda ishga tushirish
    bot_thread = threading.Thread(target=run_bot_sync, daemon=True)
    bot_thread.start()
    print("✅ Bot backgroundda ishga tushdi!")
    
    # Flask ni ishga tushirish
    port = int(os.environ.get('PORT', 5000))
    print(f"✅ Flask server ishga tushmoqda... Port: {port}")
    print("✅ Admin panel: http://localhost:5000/admin")
    print("✅ Login: admin, Parol: admin123")
    
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    start_services()