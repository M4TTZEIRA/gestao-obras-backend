from flask import Flask, send_from_directory, jsonify
import os
from .config import Config
# --- ATUALIZADO: Importa 'jwt' ---
from .extensions import db, migrate, bcrypt, cors, jwt 
from datetime import timedelta # <-- NOVO para JWT

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # --- NOVO: Configuração de tempo de expiração do JWT ---
    # A Secret Key (JWT_SECRET_KEY) já está no seu config.py
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
    # ----------------------------------------------------

    # Inicializa as extensões
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    cors.init_app(app, origins="*", supports_credentials=True)
    jwt.init_app(app) # <-- NOVO: Inicializa o JWT

    # Garante que as pastas de uploads existem
    try:
        profile_pics_path = os.path.join(app.instance_path, 'uploads/profile_pics')
        os.makedirs(profile_pics_path, exist_ok=True)
        
        checklist_pics_path = os.path.join(app.instance_path, 'uploads/checklist_pics')
        os.makedirs(checklist_pics_path, exist_ok=True)
        
        # --- Pasta para Documentos da Obra ---
        documentos_obra_path = os.path.join(app.instance_path, 'uploads/documentos_obra')
        os.makedirs(documentos_obra_path, exist_ok=True)
        # -------------------------------------
    except OSError as e:
        print(f"Erro ao criar diretório de uploads: {e}")

    # Importa os modelos DEPOIS do db.init_app
    with app.app_context():
        from . import models

    # -- Register Blueprints --
    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    from .routes.users import users_bp
    app.register_blueprint(users_bp, url_prefix='/api/users')

    from .routes.obras import obras_bp
    app.register_blueprint(obras_bp, url_prefix='/api/obras')

    from .routes.financeiro import financeiro_bp
    app.register_blueprint(financeiro_bp, url_prefix='/api') 

    from .routes.inventario import inventario_bp
    app.register_blueprint(inventario_bp, url_prefix='/api') 

    from .routes.checklist import checklist_bp
    app.register_blueprint(checklist_bp, url_prefix='/api') 
    
    from .routes.documentos import documentos_bp
    app.register_blueprint(documentos_bp, url_prefix='/api')

    # -------------------------------------

    # --- NOVO BLUEPRINT DE RELATÓRIOS ---
    from .routes.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/api')
    # ------------------------------------

    @app.route('/')
    def index():
        return "Servidor Backend Gestão de Obras no ar!"

    # --- ROTAS PARA SERVIR FICHEIROS ---
    
    @app.route('/api/uploads/profile_pics/<path:filename>')
    def serve_profile_pic(filename):
        upload_dir = os.path.join(app.instance_path, 'uploads/profile_pics')
        try:
            return send_from_directory(upload_dir, filename, as_attachment=False)
        except FileNotFoundError:
             return jsonify({"error": "Ficheiro não encontrado"}), 404
             
    @app.route('/api/uploads/checklist_pics/<path:filename>')
    def serve_checklist_pic(filename):
        upload_dir = os.path.join(app.instance_path, 'uploads/checklist_pics') 
        try:
            return send_from_directory(upload_dir, filename, as_attachment=False)
        except FileNotFoundError:
             return jsonify({"error": "Ficheiro não encontrado"}), 404
             
    # --- Rota específica para documentos da obra ---
    @app.route('/api/uploads/documentos_obra/<path:filename>')
    def serve_documento_obra(filename):
        upload_dir = os.path.join(app.instance_path, 'uploads/documentos_obra') 
        try:
            return send_from_directory(upload_dir, filename, as_attachment=False) # Visualização
        except FileNotFoundError:
             return jsonify({"error": "Ficheiro não encontrado"}), 404
    # -----------------------------------------------

    return app
