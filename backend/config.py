import os

# Encontra o caminho base do projeto
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'voce-precisa-mudar-esta-chave-secreta'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'mude-esta-chave-jwt-tambem'

    # --- A GRANDE MUDANÇA ESTÁ AQUI ---
    # 1. Procura pela URL do banco de dados na nuvem (ex: no Render)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    # 2. Se não encontrar, usa o banco de dados SQLite local
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')
    # ------------------------------------

    SQLALCHEMY_TRACK_MODIFICATIONS = False