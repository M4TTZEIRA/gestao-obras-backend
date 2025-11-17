from flask import Flask, send_from_directory, jsonify
import os
from .config import Config
from .extensions import db, migrate, bcrypt, cors, jwt 
from datetime import timedelta 

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    main_secret_key = app.config.get("SECRET_KEY", "uma-chave-secreta-muito-dificil-de-adivinhar")
    app.config["SECRET_KEY"] = main_secret_key
    app.config["JWT_SECRET_KEY"] = main_secret_key
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)

    # Inicializa as extensões
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)

    # --- CONFIGURAÇÃO DE CORS ATUALIZADA ---
    origins = [
        "http://localhost:5173", # Para o seu teste local
        "https://gestao-obras-frontend.vercel.app", # A URL principal
        "https://gestao-obras-frontend-c8lq2eiht-matheus-leocadios-projects.vercel.app", # URL antiga
        "https://gestao-obras-frontend-q9uv1hm7z-matheus-leocadios-projects.vercel.app" # <-- A SUA NOVA URL
    ]
    cors.init_app(app, origins=origins, supports_credentials=True)
    # ------------------------------------

    jwt.init_app(app) 

    # Cria pastas de uploads
    try:
        os.makedirs(os.path.join(app.instance_path, 'uploads/profile_pics'), exist_ok=True)
        os.makedirs(os.path.join(app.instance_path, 'uploads/checklist_pics'), exist_ok=True)
        os.makedirs(os.path.join(app.instance_path, 'uploads/documentos_obra'), exist_ok=True)
        os.makedirs(os.path.join(app.instance_path, 'uploads/marketplace'), exist_ok=True)
    except OSError as e:
        print(f"Erro ao criar diretório de uploads: {e}")

    with app.app_context():
        from . import models

    # -- Registra os Blueprints (Rotas) --
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

    from .routes.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix='/api')

    from .routes.marketplace import marketplace_bp
    app.register_blueprint(marketplace_bp, url_prefix='/api')

    @app.route('/')
    def index():
        return "Servidor Backend Gestão de Obras no ar!"

    # --- Rotas para servir ficheiros ---

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

    @app.route('/api/uploads/documentos_obra/<path:filename>')
    def serve_documento_obra(filename):
        upload_dir = os.path.join(app.instance_path, 'uploads/documentos_obra') 
        try:
            return send_from_directory(upload_dir, filename, as_attachment=False)
        except FileNotFoundError:
             return jsonify({"error": "Ficheiro não encontrado"}), 404

    @app.route('/api/uploads/marketplace/<path:filename>')
    def serve_marketplace_pic(filename):
        upload_dir = os.path.join(app.instance_path, 'uploads/marketplace')
        try:
            return send_from_directory(upload_dir, filename, as_attachment=False)
        except FileNotFoundError:
             return jsonify({"error": "Ficheiro não encontrado"}), 404

    return app