from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserTable(db.Model):
    __tablename__ = 'user_table'
    ID = db.Column(db.Integer, primary_key=True)          
    user_ID = db.Column(db.Text, unique=True, nullable=False) 
    password = db.Column(db.Text, nullable=False)         

class ImageAnalysis(db.Model):
    __tablename__ = 'image_analysis'
    id = db.Column(db.Integer, primary_key=True)                
    user_id = db.Column(db.Integer, db.ForeignKey('user_table.ID'), nullable=False)
    filename = db.Column(db.Text, unique=True, nullable=False)  
    caption_cn = db.Column(db.Text, nullable=False)             
    tags_cn = db.Column(db.Text, nullable=False)                
    tags_conf = db.Column(db.Text, nullable=True)