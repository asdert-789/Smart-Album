import os
from flask import Flask
from models import db
from config import config_dict
from blueprints.auth import auth_bp
from blueprints.gallery import gallery_bp
from blueprints.gallery_api import gallery_api_bp

app = Flask(__name__)

env_name = os.getenv('FLASK_ENV', 'development')
app.config.from_object(config_dict[env_name])

# 初始化資料庫
db.init_app(app)

# 註冊 Blueprint 模組
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(gallery_bp, url_prefix='/')
app.register_blueprint(gallery_api_bp, url_prefix='/')

# 自動建立資料夾與資料庫資料表
with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['YOLO_FOLDER'], exist_ok=True)

if __name__ == '__main__':
    app.run()