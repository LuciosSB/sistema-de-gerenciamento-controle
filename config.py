import os

class Config:
    #SECRET_KEY = 'geticdmtt2025'
    SECRET_KEY = '1234'

    #SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:geticdmtt2025@10.108.129.85:5432/controle_almox'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:1234@10.108.128.137:5432/controle_almox?client_encoding=utf8'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Caminho para o executável wkhtmltopdf.
    WKHTMLTOPDF_PATH = 'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'

    UPLOAD_FOLDER = 'static/uploads' 