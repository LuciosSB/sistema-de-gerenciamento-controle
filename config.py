import os

class Config:
    SECRET_KEY = '1234'

    # URI do Banco de Dados. A que você já usava.
    #SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:1234@10.108.129.70:5432/controle_almox'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:geticdmtt2025@10.108.129.85:5432/controle_almox'
    #SQLALCHEMY_DATABASE_URI = 'postgresql://admin_dmtt:senhalegal@10.108.131.12:5432/controle_almox'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Caminho para o executável wkhtmltopdf.
    WKHTMLTOPDF_PATH = 'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'