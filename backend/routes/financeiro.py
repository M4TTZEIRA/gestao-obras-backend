from flask import Blueprint, jsonify, request
from ..models import Obras, FinanceiroTransacoes, User, AuditLog
from ..extensions import db
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps

# --- Decorator de Permissão (Sem alterações) ---
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

# --- Helper para Log de Auditoria (Sem alterações) ---
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

# Cria o Blueprint
financeiro_bp = Blueprint('financeiro', __name__)

# --- Rota GET (Sem alterações) ---
@financeiro_bp.route('/obras/<int:obra_id>/financeiro/', methods=['GET'])
@jwt_required()
def get_transacoes_obra(obra_id):
    try:
        obra = Obras.query.get_or_404(obra_id)
        # Agora ordenamos por status (ativos primeiro) e depois por data
        transacoes = FinanceiroTransacoes.query.filter_by(obra_id=obra_id).order_by(FinanceiroTransacoes.status.asc(), FinanceiroTransacoes.criado_em.desc()).all()
        return jsonify([t.to_dict() for t in transacoes]), 200
    except Exception as e:
        print(f"Erro ao buscar transações financeiras da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao buscar transações."}), 500

# --- Rota POST (Sem alterações) ---
@financeiro_bp.route('/obras/<int:obra_id>/financeiro/', methods=['POST', 'OPTIONS'])
@gestor_ou_admin_required()
def add_transacao_obra(obra_id, **kwargs):
    # ... (O código desta função continua exatamente o mesmo) ...
    # ... (Ele já cria a transação com o status 'ativo' por padrão) ...
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    current_user_id = get_jwt_identity()
    obra = Obras.query.get_or_404(obra_id)
    data = request.get_json()
    if not data or not data.get('tipo') or not data.get('valor') or not data.get('descricao'):
        return jsonify({"error": "Tipo, valor e descrição são obrigatórios."}), 400
    try:
        valor = float(data.get('valor'))
        if valor <= 0:
            return jsonify({"error": "Valor deve ser positivo."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Formato de valor inválido."}), 400
    tipo = data.get('tipo')
    if tipo not in ['entrada', 'saida']:
        return jsonify({"error": "Tipo inválido (deve ser 'entrada' ou 'saida')."}), 400
    descricao = data.get('descricao')
    try:
        nova_transacao = FinanceiroTransacoes(
            obra_id=obra_id,
            tipo=tipo,
            valor=valor,
            descricao=descricao,
            criado_por=current_user_id,
            status='ativo' # Garante que o status inicial é 'ativo'
        )
        orcamento_atual_decimal = float(obra.orcamento_atual) if obra.orcamento_atual is not None else 0.0
        if tipo == 'entrada':
            obra.orcamento_atual = orcamento_atual_decimal + valor
        else:
            obra.orcamento_atual = orcamento_atual_decimal - valor
        db.session.add(nova_transacao)
        db.session.add(obra) 
        db.session.flush() 
        log_audit(
            current_user_id,
            'create',
            'FinanceiroTransacoes',
            nova_transacao.id,
            {'obra_id': obra_id, 'tipo': tipo, 'valor': valor, 'descricao': descricao}
        )
        db.session.commit()
        return jsonify(nova_transacao.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar transação financeira à obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao salvar a transação."}), 500


# --- #################################### ---
# ---        NOVA ROTA DE CANCELAMENTO     ---
# --- #################################### ---

@financeiro_bp.route('/financeiro/<int:transacao_id>/cancelar/', methods=['PUT', 'OPTIONS'])
@gestor_ou_admin_required()
def cancel_transacao(transacao_id, **kwargs):
    """
    Cancela uma transação financeira, revertendo seu valor no orçamento.
    """
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
        
    transacao = FinanceiroTransacoes.query.get_or_404(transacao_id)
    obra = Obras.query.get_or_404(transacao.obra_id)
    data = request.get_json()
    current_user_id = get_jwt_identity()

    if not data or not data.get('motivo'):
        return jsonify({"error": "O motivo do cancelamento é obrigatório."}), 400

    if transacao.status == 'cancelado':
        return jsonify({"error": "Esta transação já foi cancelada."}), 409 # 409 Conflict

    try:
        # Guarda valores para o log e recálculo
        tipo_transacao = transacao.tipo
        valor_transacao = float(transacao.valor)
        
        # --- Lógica de Recálculo do Orçamento da Obra ---
        orcamento_atual = float(obra.orcamento_atual)
        
        # Reverte o valor da transação que está sendo cancelada
        if tipo_transacao == 'entrada':
            orcamento_atual -= valor_transacao # Remove a entrada do orçamento
        else: # 'saida'
            orcamento_atual += valor_transacao # Devolve a saída ao orçamento
            
        obra.orcamento_atual = orcamento_atual
        # --- Fim do Recálculo ---

        # Atualiza a transação com os dados do cancelamento
        transacao.status = 'cancelado'
        transacao.motivo_cancelamento = data.get('motivo')
        transacao.cancelado_em = datetime.now()
        transacao.cancelado_por = current_user_id
        transacao.atualizado_em = datetime.now()

        # Log de Auditoria
        log_audit(
            current_user_id,
            'cancel', # Nova ação de log
            'FinanceiroTransacoes',
            transacao.id,
            {'motivo': data.get('motivo'), 'valor_revertido': valor_transacao}
        )
        
        db.session.add(transacao)
        db.session.add(obra)
        db.session.commit()
        
        return jsonify(transacao.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao CANCELAR transação {transacao_id}: {e}")
        return jsonify({"error": "Erro interno ao cancelar a transação."}), 500