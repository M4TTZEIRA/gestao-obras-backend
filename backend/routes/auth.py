from flask import Blueprint, request, jsonify
from ..models import User
from ..extensions import db, bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

auth_bp = Blueprint('auth', __name__)

# --- ROTA DE LOGIN (CORRIGIDA) ---
@auth_bp.route('/login', methods=['POST', 'OPTIONS']) # <-- ADICIONADO 'OPTIONS'
def login():
    # --- NOVO: Lida com a requisição de 'preflight' do CORS ---
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    # ----------------------------------------------------

    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Usuário e senha são obrigatórios"}), 400

    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Credenciais inválidas"}), 401 

    try:
        access_token = create_access_token(identity=str(user.id))
        user_data = user.to_dict()
    except Exception as e:
        print(f"Erro ao serializar usuário ou criar token (auth.py): {e}")
        return jsonify({"error": "Erro interno ao processar dados do usuário"}), 500

    return jsonify({
        "access_token": access_token, 
        "user": user_data
    }), 200

# --- Rota de Atualizar Credenciais (Sem alterações) ---
@auth_bp.route('/update-credentials', methods=['PUT', 'OPTIONS'])
@jwt_required()
def update_credentials():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    if not data or not data.get('current_password'):
        return jsonify({"error": "A senha atual é obrigatória para fazer alterações."}), 400
    current_password = data.get('current_password')
    if not user.check_password(current_password):
        return jsonify({"error": "A senha atual está incorreta."}), 403
    try:
        new_username = data.get('new_username')
        if new_username and new_username != user.username:
            if User.query.filter_by(username=new_username).first():
                return jsonify({"error": "Este nome de usuário (username) já está em uso."}), 409
            user.username = new_username
        new_password = data.get('new_password')
        if new_password:
            user.set_password(new_password)
        if new_username or new_password:
            db.session.commit()
            return jsonify({"message": "Credenciais atualizadas com sucesso!"}), 200
        else:
            return jsonify({"message": "Nenhuma alteração fornecida."}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar credenciais para user {user.id}: {e}")
        return jsonify({"error": "Erro interno ao atualizar credenciais."}), 500

# --- Rota de Primeira Mudança de Senha (Sem alterações) ---
@auth_bp.route('/first-password-change', methods=['PUT', 'OPTIONS'])
@jwt_required()
def first_password_change():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({"error": "Senha atual e nova senha são obrigatórias."}), 400
    current_password = data.get('current_password')
    if not user.check_password(current_password):
        return jsonify({"error": "A senha atual (temporária) está incorreta."}), 403
    new_password = data.get('new_password')
    if len(new_password) < 6:
         return jsonify({"error": "A nova senha deve ter pelo menos 6 caracteres."}), 400
    try:
        user.set_password(new_password)
        user.must_change_password = False
        db.session.commit()
        return jsonify(user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao forçar mudança de senha para user {user.id}: {e}")
        return jsonify({"error": "Erro interno ao salvar nova senha."}), 500