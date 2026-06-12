import os
import io
import zipfile
from flask import Blueprint, request, current_app, jsonify, url_for, session, g, send_file
from PIL import Image
from models import db, ImageAnalysis
from blueprints.ai_services import generate_blip_caption, draw_yolo_labels

gallery_api_bp = Blueprint('gallery_api', __name__)  

def remove_data(orig_path, yolo_path):
    if os.path.exists(orig_path):
        os.remove(orig_path)
    if os.path.exists(yolo_path):
        os.remove(yolo_path)

@gallery_api_bp.before_request
def load_gallery_config():
    """在執行任何相簿 API 前，自動把常用路徑塞入 g 變數中"""
    g.user_id = session.get('user_id')
    if not g.user_id:
        return jsonify({'success': False, 'error': '未登入'}), 401
    g.upload_folder = current_app.config['UPLOAD_FOLDER']
    g.yolo_folder = current_app.config['YOLO_FOLDER']

@gallery_api_bp.route('/analyze_image', methods=['POST'])
def analyze_image():
        
    filename = request.json.get('filename')
    if not filename:
        return jsonify({'error': '缺少檔名'}), 400

    img_path = os.path.join(g.upload_folder, filename)
    yolo_filename = f"yolo_{filename}"
    
    orig_image_url = url_for('static', filename=f'uploads/{filename}')
    yolo_image_url = url_for('static', filename=f'yolo_uploads/{yolo_filename}')
    
    if not os.path.exists(img_path):
        return jsonify({'error': '找不到原始圖片'}), 404

    try:
        # 【第一步】檢查資料庫紀錄
        existing_record = ImageAnalysis.query.filter_by(filename=filename, user_id=g.user_id).first()
        yolo_file_path = os.path.join(g.yolo_folder, yolo_filename)
        # 💡 優化：確保紀錄存在、且 caption_cn 不是空字串、且 YOLO 圖片實體存在
        if existing_record and existing_record.caption_cn and os.path.exists(yolo_file_path):
            # 💡 防呆安全修正：如果 tags_conf 欄位報錯或為空，改拿 tags_cn 當備用
            try:
                if hasattr(existing_record, 'tags_conf') and existing_record.tags_conf:
                    objects_list = existing_record.tags_conf.split(',')
                else:
                    objects_list = [t.strip() for t in existing_record.tags_cn.split(',') if t.strip()]
            except Exception:
                objects_list = [t.strip() for t in existing_record.tags_cn.split(',') if t.strip()]

            return jsonify({
                'success': True,
                'caption': existing_record.caption_cn,
                'objects': objects_list,
                'orig_image_url': orig_image_url,
                'yolo_image_url': yolo_image_url,
                'cached': True
            })

        # 【第二步】無有效快取，執行 AI 運算
        raw_image = Image.open(img_path).convert('RGB')
        
        # 跑 BLIP 敘述與 YOLO 偵測
        caption_cn = generate_blip_caption(raw_image)
        # detected_objects_cn 格式為：['標籤A (0.99)', '標籤B (0.87)']
        detected_objects_cn, raw_tags_for_db = draw_yolo_labels(img_path, yolo_filename, g.yolo_folder)
        
        tags_str = ",".join(raw_tags_for_db)
        tags_conf_str = ",".join(detected_objects_cn) # 💡 將帶分數的標籤轉成字串

        if existing_record:
            # 更新紀錄
            existing_record.caption_cn = caption_cn
            existing_record.tags_cn = tags_str
            existing_record.tags_conf = tags_conf_str # 💡 寫入新欄位
        else:
            # 防呆新建
            new_analysis = ImageAnalysis(
                user_id=g.user_id, 
                filename=filename, 
                caption_cn=caption_cn, 
                tags_cn=tags_str,
                tags_conf=tags_conf_str 
            )
            db.session.add(new_analysis)
            
        db.session.commit() 

        return jsonify({
            'success': True,
            'caption': caption_cn,
            'objects': detected_objects_cn, # 這裡維持原樣回傳陣列給前端
            'orig_image_url': orig_image_url,
            'yolo_image_url': yolo_image_url,
            'cached': False
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@gallery_api_bp.route('/delete_images', methods=['POST'])
def delete_images():
        
    filenames = request.json.get('filenames', [])
    if not filenames:
        return jsonify({'success': False, 'error': '未選擇任何圖片'}), 400
    
    success_count = 0
    for filename in filenames:
        # 💡 安全檢查：確保該圖片確實屬於該使用者才允許刪除
        record = ImageAnalysis.query.filter_by(filename=filename, user_id=g.user_id).first()
        if not record:
            continue
            
        orig_path = os.path.join(g.upload_folder, filename)
        yolo_path = os.path.join(g.yolo_folder, f"yolo_{filename}")
        remove_data(orig_path, yolo_path)
            
        db.session.delete(record)
        success_count += 1
        
    db.session.commit()
    return jsonify({'success': True, 'deleted_count': success_count})

@gallery_api_bp.route('/clear_all_images', methods=['POST'])
def clear_all_images():
    # 💡 唯有屬於當前登入使用者的快取紀錄才會被撈出並實體刪除
    user_records = ImageAnalysis.query.filter_by(user_id=g.user_id).all()
    for rec in user_records:
        orig_path = os.path.join(g.upload_folder, rec.filename)
        yolo_path = os.path.join(g.yolo_folder, f"yolo_{rec.filename}")
        remove_data(orig_path, yolo_path)

        db.session.delete(rec)
        
    db.session.commit()
    return jsonify({'success': True})

@gallery_api_bp.route('/download_images', methods=['POST'])
def download_images():
    data = request.get_json() or {}
    filenames = data.get('filenames', [])
    mode = data.get('mode', 'orig')  # orig 或 yolo

    if not filenames:
        return jsonify({'success': False, 'error': '未選擇任何圖片'}), 400

    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            record = ImageAnalysis.query.filter_by(
                filename=filename,
                user_id=g.user_id
            ).first()

            if not record:
                continue

            if mode == 'yolo':
                file_path = os.path.join(g.yolo_folder, f"yolo_{filename}")
                zip_name = f"analyzed_{filename}"
            else:
                file_path = os.path.join(g.upload_folder, filename)
                zip_name = f"original_{filename}"

            if os.path.exists(file_path):
                zf.write(file_path, arcname=zip_name)

    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{mode}_images.zip"
    )