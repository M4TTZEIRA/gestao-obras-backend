from flask import Blueprint, jsonify, request, current_app, send_from_directory
from ..models import Imovel, ImovelFotos, User, AuditLog
from ..extensions import db
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import uuid
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps

# --- Configurações de Upload ---
MARKETPLACE_UPLOAD_FOLDER = 'uploads/marketplace'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Decorator de Permissão (Admin/Gestor) ---
def gestor_ou_admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            if request.method == 'OPTIONS':
                return fn(*args, **kwargs)
            try:
                verify_jwt_in_request()
            except Exception as e:
                 return jsonify({"error": f"Token inválido: {str(e)}"}), 401
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            if not user or (user.role.name != 'Administrador' and user.role.name != 'Gestor'):
                return jsonify({"error": "Acesso negado."}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

marketplace_bp = Blueprint('marketplace', __name__)

# --- LISTAR IMÓVEIS (Público para quem tem login) ---
@marketplace_bp.route('/marketplace/', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_imoveis():
    if request.method == 'OPTIONS': return jsonify({'msg': 'OK'}), 200
    imoveis = Imovel.query.order_by(Imovel.criado_em.desc()).all()
    return jsonify([i.to_dict() for i in imoveis]), 200

# --- OBTER DETALHES DE UM IMÓVEL ---
@marketplace_bp.route('/marketplace/<int:id>/', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_imovel(id):
    if request.method == 'OPTIONS': return jsonify({'msg': 'OK'}), 200
    imovel = Imovel.query.get_or_404(id)
    return jsonify(imovel.to_dict()), 200

# --- CRIAR IMÓVEL (Admin/Gestor) ---
@marketplace_bp.route('/marketplace/', methods=['POST', 'OPTIONS'])
@gestor_ou_admin_required()
def create_imovel():
    if request.method == 'OPTIONS': return jsonify({'msg': 'OK'}), 200
    
    # Recebe dados via Form-Data (para aceitar imagem junto)
    data = request.form
    file = request.files.get('foto_capa')
    
    try:
        novo_imovel = Imovel(
            titulo=data.get('titulo'),
            endereco=data.get('endereco'),
            bairro=data.get('bairro'),
            numero=data.get('numero'),
            cep=data.get('cep'),
            metragem=data.get('metragem'),
            proprietario=data.get('proprietario'),
            observacoes=data.get('observacoes'),
            status=data.get('status', 'À venda'),
            criado_por=get_jwt_identity()
        )

        # Processa a Foto de Capa
        if file and allowed_file(file.filename):
            filename = secure_filename(f"capa_{uuid.uuid4()}_{file.filename}")
            upload_path = os.path.join(current_app.instance_path, MARKETPLACE_UPLOAD_FOLDER)
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))
            novo_imovel.foto_capa = filename

        db.session.add(novo_imovel)
        db.session.commit()
        return jsonify(novo_imovel.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar imóvel: {e}")
        return jsonify({"error": "Erro ao salvar imóvel"}), 500

# --- ADICIONAR FOTO NA GALERIA ---
@marketplace_bp.route('/marketplace/<int:id>/fotos/', methods=['POST', 'OPTIONS'])
@gestor_ou_admin_required()
def add_gallery_photo(id):
    if request.method == 'OPTIONS': return jsonify({'msg': 'OK'}), 200
    
    imovel = Imovel.query.get_or_404(id)
    file = request.files.get('foto')

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(f"galeria_{id}_{uuid.uuid4()}_{file.filename}")
            upload_path = os.path.join(current_app.instance_path, MARKETPLACE_UPLOAD_FOLDER)
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))

            nova_foto = ImovelFotos(imovel_id=id, filename=filename)
            db.session.add(nova_foto)
            db.session.commit()
            return jsonify(nova_foto.to_dict()), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Arquivo inválido"}), 400

# --- ATUALIZAR IMÓVEL ---
@marketplace_bp.route('/marketplace/<int:id>/', methods=['PUT', 'OPTIONS'])
@gestor_ou_admin_required()
def update_imovel(id):
    if request.method == 'OPTIONS': return jsonify({'msg': 'OK'}), 200
    imovel = Imovel.query.get_or_404(id)
    data = request.json
    
    if 'titulo' in data: imovel.titulo = data.get('titulo')
    if 'endereco' in data: imovel.endereco = data.get('endereco')
    if 'bairro' in data: imovel.bairro = data.get('bairro')
    if 'numero' in data: imovel.numero = data.get('numero')
    if 'cep' in data: imovel.cep = data.get('cep')
    if 'metragem' in data: imovel.metragem = data.get('metragem')
    if 'proprietario' in data: imovel.proprietario = data.get('proprietario')
    if 'observacoes' in data: imovel.observacoes = data.get('observacoes')
    if 'status' in data: imovel.status = data.get('status')
    
    db.session.commit()
    return jsonify(imovel.to_dict()), 200

# --- REMOVER IMÓVEL ---
@marketplace_bp.route('/marketplace/<int:id>/', methods=['DELETE', 'OPTIONS'])
@gestor_ou_admin_required()
def delete_imovel(id):
    if request.method == 'OPTIONS': return jsonify({'msg': 'OK'}), 200
    imovel = Imovel.query.get_or_404(id)
    
    # Remove arquivo de capa
    if imovel.foto_capa:
        try:
            os.remove(os.path.join(current_app.instance_path, MARKETPLACE_UPLOAD_FOLDER, imovel.foto_capa))
        except: pass
        
    # As fotos da galeria são removidas do banco pelo cascade, mas precisamos limpar os arquivos
    for foto in imovel.fotos:
        try:
            os.remove(os.path.join(current_app.instance_path, MARKETPLACE_UPLOAD_FOLDER, foto.filename))
        except: pass

    db.session.delete(imovel)
    db.session.commit()
    return '', 204