import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """基礎基礎設定"""
    # 從環境變數讀取，讀不到則使用預設值
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_fallback_secret_key')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # 資料庫路徑設定
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'user_table.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 圖片上傳路徑設定
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    YOLO_FOLDER = os.path.join(BASE_DIR, 'static', 'yolo_uploads')

class DevelopmentConfig(Config):
    """開發環境專用設定"""
    DEBUG = True

class ProductionConfig(Config):
    """線上環境專用設定"""
    DEBUG = False

config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}