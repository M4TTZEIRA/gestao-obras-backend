from flask import Blueprint, jsonify, request, current_app
from ..models import Obras, User, ObraFuncionarios, Role, AuditLog 
from ..extensions import db
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename
import shutil 
import json 
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps

# --- Decorator de Permissão ---
def gestor_ou_admin_required():
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

obras_bp = Blueprint('obras', __name__)

# --- Constantes e Helpers ---
UPLOAD_FOLDER = 'uploads/profile_pics' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_audit(user_id, action_type, resource_type, resource_id, details=None):
    try:
        log_entry = AuditLog(
            user_id=user_id, 
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details 
        )
        db.session.add(log_entry)
    except Exception as e:
        print(f"ERRO CRÍTICO ao tentar criar log de auditoria: {e}")


# --- Rota GET /api/obras/ ---
@obras_bp.route('/', methods=['GET'])
@jwt_required()
def get_obras():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        role = user.role.name if user.role else 'Prestador'
        if role == 'Administrador' or role == 'Gestor':
            obras_query = Obras.query.order_by(Obras.criado_em.desc()).all()
        else:
            obras_query = Obras.query.join(
                ObraFuncionarios, ObraFuncionarios.obra_id == Obras.id
            ).filter(
                ObraFuncionarios.user_id == current_user_id
            ).order_by(Obras.criado_em.desc()).all()
        obras = [obra.to_dict() for obra in obras_query]
        return jsonify(obras), 200
    except Exception as e:
        print(f"Erro ao buscar obras (obras.py GET): {e}")
        return jsonify({"error": "Erro interno do servidor ao processar obras"}), 500

# --- Rota POST /api/obras/ ---
@obras_bp.route('/', methods=['POST'])
@gestor_ou_admin_required()
def create_obra(**kwargs):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    if not data or not data.get('nome'):
        return jsonify({"error": "O nome da obra é obrigatório."}), 400
    try:
        nova_obra = Obras(
            nome=data.get('nome'),
            endereco=data.get('endereco'),
            proprietario=data.get('proprietario'),
            orcamento_inicial=data.get('orcamento_inicial') or 0.0,
            orcamento_atual=data.get('orcamento_inicial') or 0.0,
            status=data.get('status', 'Em Andamento'),
            criado_por=current_user_id 
        )
        db.session.add(nova_obra)
        db.session.flush()
        log_audit(current_user_id, 'create', 'Obras', nova_obra.id, {'nome': nova_obra.nome})
        db.session.commit()
        return jsonify(nova_obra.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar obra (obras.py POST): {e}")
        return jsonify({"error": "Erro interno ao salvar a obra."}), 500

# --- Rota GET /api/obras/<id>/ ---
@obras_bp.route('/<int:obra_id>/', methods=['GET'])
@jwt_required() 
def get_obra_detalhes(obra_id):
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        role = user.role.name if user.role else 'Prestador'
        obra = Obras.query.get_or_404(obra_id)
        if role == 'Prestador':
            vinculo = ObraFuncionarios.query.filter_by(
                obra_id=obra_id, 
                user_id=current_user_id
            ).first()
            if not vinculo:
                return jsonify({"error": "Acesso negado a esta obra."}), 403
        return jsonify(obra.to_dict()), 200
    except Exception as e:
        print(f"Erro ao buscar detalhes da obra (obras.py GET <id>): {e}")
        return jsonify({"error": "Erro interno ao buscar detalhes da obra."}), 500

# --- ATUALIZADA: Rota PUT /api/obras/<id>/ (EDITAR OBRA) ---
@obras_bp.route('/<int:obra_id>/', methods=['PUT', 'OPTIONS'])
@gestor_ou_admin_required()
def update_obra(obra_id, **kwargs):
    """Atualiza os dados de uma obra e registra o log de auditoria detalhado."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    obra = Obras.query.get_or_404(obra_id)
    data = request.get_json()
    current_user_id = get_jwt_identity()
    if not data:
        return jsonify({"error": "Dados da requisição não encontrados."}), 400
    try:
        alteracoes = {}
        estado_anterior = {}
        novo_nome = data.get('nome', obra.nome)
        if novo_nome != obra.nome:
            estado_anterior['nome'] = obra.nome
            alteracoes['nome'] = novo_nome
            obra.nome = novo_nome
        novo_endereco = data.get('endereco', obra.endereco)
        if novo_endereco != obra.endereco:
            estado_anterior['endereco'] = obra.endereco
            alteracoes['endereco'] = novo_endereco
            obra.endereco = novo_endereco
        novo_proprietario = data.get('proprietario', obra.proprietario)
        if novo_proprietario != obra.proprietario:
            estado_anterior['proprietario'] = obra.proprietario
            alteracoes['proprietario'] = novo_proprietario
            obra.proprietario = novo_proprietario
        novo_status = data.get('status', obra.status)
        motivo = data.get('motivo_alteracao')
        if novo_status != obra.status:
            if not motivo:
                return jsonify({"error": "O 'motivo da alteração' é obrigatório ao mudar o status da obra."}), 400
            estado_anterior['status'] = obra.status
            alteracoes['status'] = novo_status
            alteracoes['motivo_alteracao'] = motivo
            obra.status = novo_status
        if alteracoes:
            obra.atualizado_em = datetime.now()
            db.session.add(obra)
            log_audit(
                current_user_id,
                'update',
                'Obras',
                obra.id,
                {'antes': estado_anterior, 'depois': alteracoes}
            )
            db.session.commit()
        return jsonify(obra.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao ATUALIZAR obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao atualizar a obra."}), 500

# --- ATUALIZADA: Rota DELETE /api/obras/<id>/ (REMOVER OBRA) ---
@obras_bp.route('/<int:obra_id>/', methods=['DELETE', 'OPTIONS'])
@gestor_ou_admin_required() 
def delete_obra(obra_id, **kwargs):
    """Remove uma obra e todos os seus dados vinculados (cascade)"""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    obra = Obras.query.get_or_404(obra_id)
    current_user_id = get_jwt_identity()
    try:
        log_audit(
            current_user_id,
            'delete',
            'Obras',
            obra.id,
            {'removido': obra.to_dict()}
        )
        db.session.delete(obra)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao REMOVER obra {obra_id}: {e}")
        if 'FOREIGN KEY constraint failed' in str(e):
             return jsonify({"error": "Erro de integridade: Não foi possível remover a obra."}), 409
        return jsonify({"error": "Erro interno ao remover a obra."}), 500
        
# --- NOVA ROTA (LOG DE AUDITORIA) ---
@obras_bp.route('/<int:obra_id>/audit_logs/', methods=['GET', 'OPTIONS'])
@gestor_ou_admin_required()
def get_obra_audit_logs(obra_id, **kwargs):
    """Busca o histórico de alterações para uma OBRA específica."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    Obras.query.get_or_404(obra_id)
    try:
        logs = AuditLog.query.filter_by(
            resource_type='Obras',
            resource_id=obra_id
        ).order_by(AuditLog.timestamp.desc()).all()
        logs_data = []
        for log in logs:
            user_nome = log.user.nome if log.user else "Sistema"
            logs_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'action_type': log.action_type,
                'user_nome': user_nome,
                'details': log.details
            })
        return jsonify(logs_data), 200
    except Exception as e:
        print(f"Erro ao buscar logs de auditoria para obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao buscar o histórico de alterações."}), 500

# --- #################################### ---
# --- ROTAS DE FUNCIONÁRIOS (Sem alterações) ---
# --- #################################### ---

# --- Rota GET /api/obras/<id>/funcionarios/ ---
@obras_bp.route('/<int:obra_id>/funcionarios/', methods=['GET'])
@jwt_required()
def get_funcionarios_da_obra(obra_id):
    # ... (código existente sem alterações) ...
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        role = user.role.name if user.role else 'Prestador'
        obra = Obras.query.get_or_404(obra_id)
        if role == 'Prestador':
            vinculo = ObraFuncionarios.query.filter_by(
                obra_id=obra_id, 
                user_id=current_user_id
            ).first()
            if not vinculo:
                return jsonify({"error": "Acesso negado a esta obra."}), 403
        vinculos = ObraFuncionarios.query.filter_by(obra_id=obra_id).all()
        funcionarios_data = [vinculo.to_dict() for vinculo in vinculos]
        return jsonify(funcionarios_data), 200
    except Exception as e:
        print(f"Erro ao buscar funcionários da obra {obra_id} (obras.py GET func): {e}")
        return jsonify({"error": "Erro interno ao buscar funcionários."}), 500

# --- Rota POST /api/obras/<id>/funcionarios/ ---
@obras_bp.route('/<int:obra_id>/funcionarios/', methods=['POST'])
@gestor_ou_admin_required() # <-- Decorator atualizado
def adicionar_funcionario_obra(obra_id, **kwargs):
    # ... (código existente sem alterações) ...
    current_user_id = get_jwt_identity()
    obra = Obras.query.get_or_404(obra_id)
    form_data = request.form
    if not form_data:
         return jsonify({"error": "Dados do formulário não encontrados."}), 400
    is_cadastrado_str = form_data.get('is_cadastrado', 'false').lower()
    is_cadastrado = is_cadastrado_str == 'true'
    cargo = form_data.get('cargo')
    salario_str = form_data.get('salario', '0.0')
    prazo_limite_str = form_data.get('prazo_limite')
    status_pagamento = form_data.get('status_pagamento', 'À combinar')
    try:
        salario = float(salario_str) if salario_str else 0.0
    except ValueError:
        return jsonify({"error": "Formato de salário inválido."}), 400
    prazo_limite = None
    if prazo_limite_str:
        try:
            prazo_limite = date.fromisoformat(prazo_limite_str)
        except ValueError:
             return jsonify({"error": "Formato de data inválido para prazo limite (use YYYY-MM-DD)."}), 400
    novo_vinculo = ObraFuncionarios(
        obra_id=obra_id,
        cargo=cargo,
        salario=salario,
        prazo_limite=prazo_limite,
        status_pagamento=status_pagamento
    )
    audit_details = {
        'cargo': cargo,
        'salario': salario,
        'prazo_limite': prazo_limite_str,
        'status_pagamento': status_pagamento
    }
    try:
        if is_cadastrado:
            user_id = form_data.get('user_id')
            if not user_id:
                return jsonify({"error": "ID do usuário é obrigatório para funcionário cadastrado."}), 400
            user = User.query.get(user_id)
            if not user:
                 return jsonify({"error": f"Usuário com ID {user_id} não encontrado."}), 404
            novo_vinculo.user_id = user_id
            audit_details['user_id'] = user_id
            audit_details['nome'] = user.nome
        else:
            nome_nao_cadastrado = form_data.get('nome_nao_cadastrado')
            cpf_nao_cadastrado = form_data.get('cpf_nao_cadastrado')
            if not nome_nao_cadastrado:
                 return jsonify({"error": "Nome é obrigatório para funcionário não cadastrado."}), 400
            novo_vinculo.nome_nao_cadastrado = nome_nao_cadastrado
            novo_vinculo.cpf_nao_cadastrado = cpf_nao_cadastrado
            audit_details['nome_nao_cadastrado'] = nome_nao_cadastrado
            audit_details['cpf_nao_cadastrado'] = cpf_nao_cadastrado
            foto_file = request.files.get('photo')
            if foto_file and allowed_file(foto_file.filename):
                filename = secure_filename(f"func_nao_cad_{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto_file.filename}")
                upload_path_full = os.path.join(current_app.instance_path, UPLOAD_FOLDER)
                os.makedirs(upload_path_full, exist_ok=True)
                save_path = os.path.join(upload_path_full, filename)
                foto_file.save(save_path)
                novo_vinculo.foto_path_nao_cadastrado = filename
                audit_details['foto_adicionada'] = filename
            elif foto_file:
                return jsonify({"error": "Tipo de ficheiro da foto não permitido."}), 400
        db.session.add(novo_vinculo)
        db.session.flush()
        log_audit(current_user_id, 'create', 'ObraFuncionarios', novo_vinculo.id, audit_details)
        db.session.commit()
        return jsonify(novo_vinculo.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar funcionário à obra {obra_id} (obras.py POST func): {e}")
        if 'UNIQUE constraint failed' in str(e):
             return jsonify({"error": "Erro de duplicação. Verifique se este vínculo já existe."}), 409
        return jsonify({"error": "Erro interno ao salvar o vínculo do funcionário."}), 500

# --- Rota PUT /api/obras/<obra_id>/funcionarios/<vinculo_id>/ ---
@obras_bp.route('/<int:obra_id>/funcionarios/<int:vinculo_id>/', methods=['PUT', 'OPTIONS'])
@gestor_ou_admin_required() # <-- Decorator atualizado
def editar_funcionario_obra(obra_id, vinculo_id, **kwargs):
    # ... (código existente sem alterações) ...
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    current_user_id = get_jwt_identity()
    obra = Obras.query.get_or_404(obra_id)
    vinculo = ObraFuncionarios.query.filter_by(id=vinculo_id, obra_id=obra_id).first_or_404()
    data = request.get_json()
    if not data:
         data = request.form
         if not data:
              return jsonify({"error": "Dados não encontrados na requisição."}), 400
    antes = {
        'cargo': vinculo.cargo,
        'salario': str(vinculo.salario) if vinculo.salario else None,
        'prazo_limite': vinculo.prazo_limite.isoformat() if vinculo.prazo_limite else None,
        'status_pagamento': vinculo.status_pagamento,
        'nome_nao_cadastrado': vinculo.nome_nao_cadastrado if vinculo.user_id is None else None,
        'cpf_nao_cadastrado': vinculo.cpf_nao_cadastrado if vinculo.user_id is None else None,
    }
    antes = {k: v for k, v in antes.items() if v is not None}
    try:
        alteracoes_feitas = {}
        novo_cargo = data.get('cargo', vinculo.cargo)
        if novo_cargo != vinculo.cargo:
            vinculo.cargo = novo_cargo
            alteracoes_feitas['cargo'] = novo_cargo
        if 'salario' in data:
            try:
                novo_salario = float(data.get('salario'))
                if novo_salario != vinculo.salario:
                    vinculo.salario = novo_salario
                    alteracoes_feitas['salario'] = novo_salario
            except (ValueError, TypeError):
                 return jsonify({"error": "Formato de salário inválido."}), 400
        if 'prazo_limite' in data:
            novo_prazo_str = data.get('prazo_limite')
            novo_prazo = None
            if novo_prazo_str:
                try:
                    novo_prazo = date.fromisoformat(novo_prazo_str)
                except ValueError:
                    return jsonify({"error": "Formato de data inválido para prazo limite (use YYYY-MM-DD)."}), 400
            if novo_prazo != vinculo.prazo_limite:
                 vinculo.prazo_limite = novo_prazo
                 alteracoes_feitas['prazo_limite'] = novo_prazo_str
        if 'status_pagamento' in data:
            novo_status = data.get('status_pagamento', vinculo.status_pagamento)
            if novo_status != 'Atrasado' and novo_status != vinculo.status_pagamento:
                 vinculo.status_pagamento = novo_status
                 alteracoes_feitas['status_pagamento'] = novo_status
        if vinculo.user_id is None:
            novo_nome = data.get('nome_nao_cadastrado', vinculo.nome_nao_cadastrado)
            if novo_nome != vinculo.nome_nao_cadastrado:
                vinculo.nome_nao_cadastrado = novo_nome
                alteracoes_feitas['nome_nao_cadastrado'] = novo_nome
            novo_cpf = data.get('cpf_nao_cadastrado', vinculo.cpf_nao_cadastrado)
            if novo_cpf != vinculo.cpf_nao_cadastrado:
                 vinculo.cpf_nao_cadastrado = novo_cpf
                 alteracoes_feitas['cpf_nao_cadastrado'] = novo_cpf
        if alteracoes_feitas:
            log_audit(current_user_id, 'update', 'ObraFuncionarios', vinculo_id, {'antes': antes, 'depois': alteracoes_feitas})
        db.session.commit()
        return jsonify(vinculo.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao editar funcionário {vinculo_id} da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao atualizar o vínculo do funcionário."}), 500

# --- Rota DELETE /api/obras/<obra_id>/funcionarios/<vinculo_id>/ ---
@obras_bp.route('/<int:obra_id>/funcionarios/<int:vinculo_id>/', methods=['DELETE', 'OPTIONS'])
@gestor_ou_admin_required() # <-- Decorator atualizado
def remover_funcionario_obra(obra_id, vinculo_id, **kwargs):
    # ... (código existente sem alterações) ...
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    current_user_id = get_jwt_identity()
    obra = Obras.query.get_or_404(obra_id)
    vinculo = ObraFuncionarios.query.filter_by(id=vinculo_id, obra_id=obra_id).first_or_404()
    antes = vinculo.to_dict()
    try:
        foto_a_remover = None
        if vinculo.user_id is None and vinculo.foto_path_nao_cadastrado:
            foto_a_remover = vinculo.foto_path_nao_cadastrado
        log_audit(current_user_id, 'delete', 'ObraFuncionarios', vinculo_id, {'removido': antes})
        db.session.delete(vinculo)
        db.session.commit()
        if foto_a_remover:
            try:
                file_path = os.path.join(current_app.instance_path, UPLOAD_FOLDER, foto_a_remover)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as file_e:
                print(f"Aviso: Não foi possível remover o ficheiro {foto_a_remover} após exclusão do vínculo {vinculo_id}: {file_e}")
        return '', 204
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover funcionário {vinculo_id} da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao remover o vínculo do funcionário."}), 500

# --- Rota GET /api/obras/<obra_id>/funcionarios/<vinculo_id>/audit_logs/ ---
@obras_bp.route('/<int:obra_id>/funcionarios/<int:vinculo_id>/audit_logs/', methods=['GET'])
@gestor_ou_admin_required() # <-- Decorator atualizado
def get_funcionario_audit_logs(obra_id, vinculo_id, **kwargs):
    # ... (código existente sem alterações) ...
    obra = Obras.query.get_or_404(obra_id)
    vinculo = ObraFuncionarios.query.filter_by(id=vinculo_id, obra_id=obra_id).first_or_404()
    try:
        logs = AuditLog.query.filter_by(
            resource_type='ObraFuncionarios',
            resource_id=vinculo_id
        ).order_by(AuditLog.timestamp.desc()).all()
        logs_data = []
        for log in logs:
            user_nome = log.user.nome if log.user else "Sistema"
            logs_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'action_type': log.action_type,
                'user_nome': user_nome,
                'details': log.details
            })
        return jsonify(logs_data), 200
    except Exception as e:
        print(f"Erro ao buscar logs de auditoria para vínculo {vinculo_id}: {e}")
        return jsonify({"error": "Erro interno ao buscar o histórico de alterações."}), 500