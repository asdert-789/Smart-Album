import os
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator

print("正在載入 AI 模型與翻譯器...")
yolo_model = YOLO("yolov8n.pt") 
blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
translator = GoogleTranslator(source='en', target='zh-TW')
print("AI 系統準備就緒！")

def generate_blip_caption(raw_image):
    """產出圖片的英文敘述並翻譯為中文"""
    inputs = blip_processor(raw_image, return_tensors="pt")
    out = blip_model.generate(**inputs)
    caption_en = blip_processor.decode(out[0], skip_special_tokens=True)
    return translator.translate(caption_en)

def draw_yolo_labels(img_path, yolo_filename, yolo_folder):
    """執行 YOLO 偵測，動態根據圖片比例繪製粗框與中文文字標籤，並存入指定資料夾"""
    raw_image = Image.open(img_path).convert('RGB')
    img_w, img_h = raw_image.size
    
    draw_image = raw_image.copy()
    draw = ImageDraw.Draw(draw_image)
    
    # 動態調整粗細與大小
    base_scale = max(img_w, img_h) / 1000.0
    line_width = max(3, int(5 * base_scale))
    font_size = max(14, int(18 * base_scale))
    
    # 自動尋找系統中文字型
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/droid/DroidSansFallback.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:\\Windows\\Fonts\\msjh.ttc",
        "Arial Unicode.ttf"
    ]
    font = ImageFont.truetype("C:\\Windows\\Fonts\\msjh.ttc", font_size)
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except:
                continue
    if font is None:
        font = ImageFont.load_default()

    detected_objects_cn = []
    raw_tags_for_db = []

    results = yolo_model(raw_image)
    result = results[0]
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        conf = box.conf[0].item()
        cls_id = int(box.cls[0].item())
        label_en = result.names[cls_id]
        label_cn = translator.translate(label_en)
        
        tag_text = f"{label_cn} ({conf:.2f})"
        detected_objects_cn.append(tag_text)
        if label_cn not in raw_tags_for_db:
            raw_tags_for_db.append(label_cn)
            
        # 繪製粗邊框
        draw.rectangle([x1, y1, x2, y2], outline="#ff7e47", width=line_width)
        
        # 繪製文字標籤與背景
        text_bbox = draw.textbbox((0, 0), tag_text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        bg_margin = max(4, int(2 * base_scale))
        draw.rectangle([x1, y1 - text_h - (bg_margin * 2), x1 + text_w + (bg_margin * 2), y1], fill="#ff7e47")
        draw.text((x1 + bg_margin, y1 - text_h - bg_margin - 2), tag_text, fill="white", font=font)

    draw_image.save(os.path.join(yolo_folder, yolo_filename))
    return detected_objects_cn, raw_tags_for_db

def get_live_tags_with_conf(filename_or_path):
    filename = os.path.basename(filename_or_path)
    # 引入 Model 進行查詢
    from models import ImageAnalysis
    record = ImageAnalysis.query.filter_by(filename=filename).first()
    
    if record and record.tags_conf:
        return record.tags_conf.split(',')
    return []