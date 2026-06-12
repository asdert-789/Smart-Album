import os
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify, g
from models import db, ImageAnalysis
from werkzeug.utils import secure_filename

gallery_bp = Blueprint('gallery', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== 全域攔截與登入 ====================
@gallery_bp.before_request
def check_user_login():
    """自動將 user_id 塞入 g，並精準攔截非公開請求"""
    g.user_id = session.get('user_id')
    
    if not g.user_id:
        if request.path in ['/get_all_tags', '/search_tags', '/analyze_image']:
            return jsonify({'success': False, 'message': '請先登入'}), 401
            
        elif request.path not in {'/', '/gallery'}:
            flash('請先登入系統！', 'danger')
            return redirect(url_for('auth.login'))

# ==================== 1. 全新門面首頁路由 ====================
@gallery_bp.route('/')
def home():
    if g.user_id: 
        return redirect(url_for('gallery.index'))
    return render_template('home.html')

# ==================== 2. 相簿主功能頁 ====================
@gallery_bp.route('/gallery')
def index():
    images = []
    ai_data = None
    preview = None

    analysis_records = ImageAnalysis.query.filter_by(user_id=g.user_id).all()  # 💡 改用 g.user_id
    images = [rec.filename for rec in analysis_records]
        
    images.sort()
    
    preview = request.args.get('preview')
    if not preview or preview not in images:
        preview = images[0] if images else None
        
    if preview:
        ai_data = ImageAnalysis.query.filter_by(filename=preview, user_id=g.user_id).first()  # 💡 改用 g.user_id
    
    return render_template('index.html', images=images, preview=preview, ai_data=ai_data)

# ==================== 3. 多標籤智慧篩選 API ====================
@gallery_bp.route('/search_tags', methods=['POST'])
def search_tags():
    data = request.get_json() or {}
    target_tags = data.get('tags', [])       
    search_logic = data.get('logic', 'AND')  
    
    if not target_tags:
        return jsonify({'success': False, 'message': '未提供搜尋標籤'}), 400
        
    try:
        conditions = []
        for tag in target_tags:
            conditions.append(ImageAnalysis.tags_cn.like(f"%{tag}%"))
        
        if search_logic == 'AND':
            final_query = ImageAnalysis.query.filter(
                ImageAnalysis.user_id == g.user_id,  # 💡 改用 g.user_id
                *conditions
            )
        else:
            from sqlalchemy import or_
            final_query = ImageAnalysis.query.filter(
                ImageAnalysis.user_id == g.user_id,  # 💡 改用 g.user_id
                or_(*conditions)
            )
            
        records = final_query.all()
        matched_filenames = [rec.filename for rec in records]
                
        return jsonify({
            'success': True,
            'matched_images': matched_filenames
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== 4. 獲取用戶所有標籤 ====================
@gallery_bp.route('/get_all_tags', methods=['GET'])
def get_all_tags():
    try:
        records = ImageAnalysis.query.filter(
            ImageAnalysis.user_id == g.user_id,
            ImageAnalysis.tags_cn != ""
        ).all()
        
        all_tags_set = set()
        for rec in records:
            raw_tags = [t.strip() for t in rec.tags_cn.split(',') if t.strip()]
            for t in raw_tags:
                clean_tag = re.sub(r'[\s\(\):_]*[0-9\.]+\s*[\)]*', '', t).strip()
                if clean_tag and not clean_tag.replace('.','',1).isdigit():
                    all_tags_set.add(clean_tag)
                    
        return jsonify({
            'success': True,
            'tags': sorted(list(all_tags_set))
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'tags': []}), 500

# ==================== 5. 上傳圖片 ====================
@gallery_bp.route('/upload', methods=['POST'])
def upload_image():
    files = request.files.getlist('image')
    if not files or files[0].filename == '':
        flash('沒有選擇檔案！', 'danger')
        return redirect(url_for('gallery.index'))
    
    success_count = 0
    last_filename = None
    
    try:
        for file in files:
            if file and allowed_file(file.filename):
                raw_filename = secure_filename(file.filename) 
                if raw_filename.startswith('yolo_'):
                    raw_filename = raw_filename.replace('yolo_', '')
                    
                filename = f"user_{g.user_id}_{raw_filename}"
                
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                
                existing = ImageAnalysis.query.filter_by(filename=filename, user_id=g.user_id).first()
                if not existing:
                    new_analysis = ImageAnalysis(
                        user_id=g.user_id,
                        filename=filename,
                        caption_cn="",  
                        tags_cn=""
                    )
                    db.session.add(new_analysis)
                
                success_count += 1
                last_filename = filename
                
        if success_count > 0:
            db.session.commit()  
            flash(f'成功上傳 {success_count} 張圖片！', 'success')
            return redirect(url_for('gallery.index', preview=last_filename))
            
    except Exception as e:
        db.session.rollback()  
        flash(f'上傳失敗，錯誤原因: {str(e)}', 'danger')
        return redirect(url_for('gallery.index'))
    
    return redirect(url_for('gallery.index'))