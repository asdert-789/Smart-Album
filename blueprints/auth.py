import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, UserTable

auth_bp = Blueprint('auth', __name__)

# 檢查 Email 格式的正規表達式
EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 後端限制驗證：必須為 Email 格式
        if not re.match(EMAIL_REGEX, email):
            flash('帳號必須是正確的 Email 格式！', 'danger')
            return redirect(url_for('auth.login'))
            
        # 修正：改用 user_ID 進行資料庫查詢
        user = UserTable.query.filter_by(user_ID=email).first()
        
        # 這裡為了展示安全，假設您資料庫內的密碼是透過 werkzeug 加密的
        # 如果您原本的舊資料(如 admin/123456)是明文，可改為 user.password == password
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.ID
            session['user_email'] = user.user_ID
            flash('登入成功！', 'success')
            return redirect(url_for('gallery.index'))
        else:
            flash('帳號或密碼錯誤！', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not re.match(EMAIL_REGEX, email):
            flash('帳號必須是正確的 Email 格式！', 'danger')
            return redirect(url_for('auth.register'))
            
        # 修正：檢查 user_ID 是否已存在
        if UserTable.query.filter_by(user_ID=email).first():
            flash('該 Email 已被註冊！', 'danger')
            return redirect(url_for('auth.register'))
            
        # 建立新帳號並加密密碼，儲存至 user_ID 欄位
        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = UserTable(user_ID=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('註冊成功，請登入！', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('已成功登出！', 'info')
    return redirect(url_for('gallery.index'))