from flask import Blueprint, request, jsonify, current_app
from ..models import User, Role, AuditLog # <-- Importei o AuditLog
from ..extensions import db, bcrypt
import os
from werkzeug.utils import secure_filename
from datetime import datetime
# --- IMPORTS ATUALIZADOS ---
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps 
from sqlalchemy.exc import IntegrityError # <-- Importei o IntegrityError
# ---------------------------

# --- NOVO: Decorator de Permissão (Gestor ou Admin) ---
def gestor_ou_admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            # Ignora o token check para requisições OPTIONS
            if request.method == 'OPTIONS':
                return fn(*args, **kwargs)
            try:
                verify_jwt_in_request()
            except Exception as e:
                 return jsonify({"error": f"Token inválido ou ausente: {str(e)}"}), 401
                 
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user:
                 return jsonify({"error": "Usuário do token não encontrado."}), 404
            
            role = user.role.name if user.role else None
            
            if role == 'Administrador' or role == 'Gestor':
                kwargs['current_user'] = user 
                return fn(*args, **kwargs) 
            else:
                return jsonify({"error": "Acesso negado: Requer permissão de Gestor ou Administrador."}), 403
        return decorator
    return wrapper
# ------------------------------------

# --- Decorator de Admin (Sem alterações) ---
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            if request.method == 'OPTIONS':
                return fn(*args, **kwargs)
            
            try:
                verify_jwt_in_request()
            except Exception as e:
                 return jsonify({"error": f"Token inválido ou ausente: {str(e)}"}), 401

            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if user and user.role and user.role.name == 'Administrador':
                return fn(*args, **kwargs)
            else:
                return jsonify({"error": "Acesso negado: Requer permissão de Administrador."}), 403
        return decorator
    return wrapper
# ------------------------------------

users_bp = Blueprint('users', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Rota POST /api/users (Criar Usuário) (Sem alterações) ---
@users_bp.route('/', methods=['POST'])
@admin_required()
def create_user():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password') or not data.get('email') or not data.get('nome'):
        return jsonify({"error": "Nome de usuário, senha, nome e e-mail são obrigatórios"}), 400
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    nome = data.get('nome')
    role_name = data.get('role', 'Prestador')
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Nome de usuário já existe"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "E-mail já cadastrado"}), 409
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        print(f"Role '{role_name}' não encontrada, verificando se o seed foi executado.")
        return jsonify({"error": f"Role '{role_name}' inválida ou não encontrada."}), 400
    try:
        cpf_data = data.get('cpf')
        rg_data = data.get('rg')
        telefone_data = data.get('telefone')
        new_user = User(
            username=username,
            nome=nome,
            email=email,
            role_id=role.id,
            cpf=cpf_data if cpf_data else None,
            rg=rg_data if rg_data else None,
            telefone=telefone_data if telefone_data else None,
            must_change_password=True
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify(new_user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar usuário (users.py): {e}")
        return jsonify({"error": "Erro interno ao salvar o usuário."}), 500

# --- Rota GET /api/users (Listar Usuários) (ATUALIZADA) ---
@users_bp.route('/', methods=['GET'])
@gestor_ou_admin_required() # <-- DECORATOR CORRIGIDO
def get_users(**kwargs): # <-- ADICIONADO **kwargs
    """Lista todos os usuários."""
    try:
        users = User.query.all()
        return jsonify({"users": [user.to_dict() for user in users]}), 200
    except Exception as e:
        print(f"Erro ao buscar usuários (users.py GET): {e}")
        return jsonify({"error": "Erro interno ao buscar usuários."}), 500

# --- Rota GET /api/users/roles/ (Sem alterações) ---
@users_bp.route('/roles/', methods=['GET'])
@jwt_required()
def get_roles():
    """Busca todos os cargos (roles) disponíveis."""
    try:
        roles = Role.query.order_by(Role.name).all()
        return jsonify([role.to_dict() for role in roles]), 200
    except Exception as e:
        print(f"Erro ao buscar cargos (users.py GET /roles/): {e}")
        return jsonify({"error": "Erro interno ao buscar cargos."}), 500

# --- Rota GET /api/users/<id> (Buscar Usuário Específico) (Sem alterações) ---
@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role.name != 'Administrador' and str(current_user_id) != str(user_id):
        return jsonify({"error": "Acesso negado."}), 403
    user_to_get = User.query.get_or_404(user_id)
    return jsonify(user_to_get.to_dict(include_details=True)), 200

# --- Rota PUT /api/users/<id> (Atualizar Usuário) (Sem alterações) ---
@users_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user_id = get_jwt_identity()
    user_making_request = User.query.get(current_user_id)
    if user_making_request.role.name != 'Administrador' and str(current_user_id) != str(user_id):
        return jsonify({"error": "Acesso negado: Você só pode editar seu próprio perfil."}), 403
    user_to_update = User.query.get_or_404(user_id)
    data = request.get_json()
    if 'nome' in data:
        user_to_update.nome = data['nome']
    if 'email' in data:
        if data['email'] != user_to_update.email and User.query.filter_by(email=data['email']).first():
             return jsonify({"error": "E-mail já cadastrado"}), 409
        user_to_update.email = data['email']
    if 'telefone' in data:
        user_to_update.telefone = data['telefone'] if data['telefone'] else None
    if 'cpf' in data: 
        if data['cpf'] and data['cpf'] != user_to_update.cpf and User.query.filter_by(cpf=data['cpf']).first():
             return jsonify({"error": "CPF já cadastrado"}), 409
        user_to_update.cpf = data['cpf'] if data['cpf'] else None
    if 'rg' in data: 
        if data['rg'] and data['rg'] != user_to_update.rg and User.query.filter_by(rg=data['rg']).first():
             return jsonify({"error": "RG já cadastrado"}), 409
        user_to_update.rg = data['rg'] if data['rg'] else None
    if 'role' in data and user_making_request.role.name == 'Administrador':
        role = Role.query.filter_by(name=data['role']).first()
        if not role:
             return jsonify({"error": f"Role '{data['role']}' inválida."}), 400
        user_to_update.role_id = role.id
    try:
        db.session.commit()
        return jsonify(user_to_update.to_dict(include_details=True)), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar usuário {user_id} (users.py PUT): {e}")
        return jsonify({"error": "Erro interno ao atualizar usuário."}), 500

# --- Rota DELETE /api/users/<id> (Deletar Usuário) (Sem alterações) ---
@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required() 
def delete_user(user_id):
    current_user_id = get_jwt_identity()
    if str(current_user_id) == str(user_id):
        return jsonify({"error": "Você não pode deletar a si mesmo."}), 403
    user = User.query.get_or_404(user_id)
    try:
        AuditLog.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        return '', 204
    except IntegrityError as e:
        db.session.rollback()
        print(f"Erro de integridade ao deletar usuário {user_id}: {e}")
        return jsonify({"error": "Não é possível deletar este usuário. Ele ainda está vinculado a outros registros."}), 409
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao deletar usuário {user_id} (users.py DELETE): {e}")
        return jsonify({"error": "Erro interno ao deletar o usuário."}), 500

# --- ROTA: PUT /api/users/<id>/photo (Upload Foto de Perfil) (Sem alterações) ---
@users_bp.route('/<int:user_id>/photo', methods=['PUT'])
@jwt_required()
def update_user_photo(user_id):
    current_user_id = get_jwt_identity()
    user_making_request = User.query.get(current_user_id)
    if user_making_request.role.name != 'Administrador' and str(current_user_id) != str(user_id):
        return jsonify({"error": "Acesso negado: Você só pode editar sua própria foto."}), 403
    user = User.query.get_or_404(user_id)
    if 'photo' not in request.files:
        return jsonify({"error": "Nenhum ficheiro de foto enviado."}), 400
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"error": "Nenhum ficheiro selecionado."}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(f"user_{user.id}_{datetime.now().timestamp()}{os.path.splitext(file.filename)[1]}")
        upload_folder = os.path.join(current_app.instance_path, 'uploads', 'profile_pics')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        try:
            file.save(filepath)
            user.foto_path = filename 
            db.session.commit()
            return jsonify(user.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao guardar foto para user {user_id}: {e}")
            return jsonify({"error": "Erro interno ao guardar a foto."}), 500
    else:
        return jsonify({"error": "Tipo de ficheiro inválido. Permitidos: png, jpg, jpeg, gif"}), 400