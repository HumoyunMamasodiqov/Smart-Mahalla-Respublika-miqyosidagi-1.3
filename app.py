from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import threading
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

# Render uchun environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'humoyun-tezsot-2025')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Telegram bot tokeni environment variable dan
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
        
        # Agar admin mavjud bo'lmasa, yangi yaratish
        if not Admin.query.filter_by(username='admin').first():
            admin_user = Admin(username='admin', password='admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Admin foydalanuvchi yaratildi")

# Admin login
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
            return '''
            <div style="color: red; text-align: center; margin: 50px;">
                <h2>Login yoki parol xato!</h2>
                <a href="/login">Qaytadan urinish</a>
            </div>
            '''
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <style>
            body { font-family: Arial; background: #f5f5f5; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .login-form { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; width: 100%; }
        </style>
    </head>
    <body>
        <div class="login-form">
            <h2>Admin Login</h2>
            <form method="post">
                <input type="text" name="username" placeholder="Username" value="admin" required>
                <input type="password" name="password" placeholder="Password" value="admin123" required>
                <button type="submit">Kirish</button>
            </form>
        </div>
    </body>
    </html>
    '''

# Admin paneli
@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    viloyatlar = Viloyat.query.filter_by(is_active=True).all()
    return render_template('admin.html', viloyatlar=viloyatlar)

# Logout
@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

# Yangi viloyat qo'shish
@app.route('/add_viloyat', methods=['POST'])
def add_viloyat():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    name = request.form['name'].strip()
    
    if name:
        # Tekshirish: bunday viloyat mavjudmi?
        existing_viloyat = Viloyat.query.filter_by(name=name).first()
        if not existing_viloyat:
            yangi_viloyat = Viloyat(name=name)
            db.session.add(yangi_viloyat)
            db.session.commit()
            print(f"✅ Yangi viloyat qo'shildi: {name}")
        else:
            # Agar mavjud bo'lsa, faollashtirish
            existing_viloyat.is_active = True
            db.session.commit()
            print(f"✅ Viloyat faollashtirildi: {name}")
    
    return redirect(url_for('admin_panel'))

# Viloyatni o'chirish
@app.route('/delete_viloyat/<int:id>')
def delete_viloyat(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    viloyat = Viloyat.query.get(id)
    if viloyat:
        viloyat_name = viloyat.name
        viloyat.is_active = False
        db.session.commit()
        print(f"✅ Viloyat o'chirildi: {viloyat_name}")
    
    return redirect(url_for('admin_panel'))

# Viloyatlarni JSON formatida qaytarish (Telegram bot uchun)
@app.route('/api/viloyatlar')
def get_viloyatlar():
    viloyatlar = Viloyat.query.filter_by(is_active=True).all()
    viloyat_list = [{'id': v.id, 'name': v.name} for v in viloyatlar]
    return jsonify(viloyat_list)

# Bosh sahifa
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
        # Render URL dan viloyatlarni olish
        base_url = os.environ.get('RENDER_URL', 'http://localhost:5000')
        response = requests.get(f'{base_url}/api/viloyatlar')
        
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

def run_bot():
    """Botni ishga tushirish"""
    try:
        # Yangi event loop yaratish
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Bot application yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("viloyatlar", viloyatlar_command))

        print("✅ Telegram bot ishga tushdi!")
        
        # Botni ishga tushirish
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Botda xatolik: {e}")

if __name__ == '__main__':
    # Jadvallarni yaratish
    create_tables()
    
    # Botni alohida threadda ishga tushirish (faqat localda)
    if os.environ.get('RENDER') != 'true':
        try:
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            print("✅ Bot thread ishga tushdi!")
        except Exception as e:
            print(f"❌ Bot threadida xatolik: {e}")
    
    # Flask serverni ishga tushirish
    port = int(os.environ.get('PORT', 5000))
    print(f"✅ Flask server ishga tushmoqda... Port: {port}")
    print("✅ Admin panel: /admin")
    print("✅ Login: admin")
    print("✅ Parol: admin123")
    print("✅ API endpoint: /api/viloyatlar")
    
    app.run(host='0.0.0.0', port=port, debug=False)