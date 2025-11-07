from flask import Blueprint, jsonify, request # <-- 'request' FOI ADICIONADO AQUI
from ..models import Obras, InventarioItens, AuditLog, User
from ..extensions import db
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps

# --- Decorator de Permissão (CORRIGIDO) ---
def gestor_ou_admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            # --- CORREÇÃO: Ignora o token check para requisições OPTIONS ---
            if request.method == 'OPTIONS':
                return fn(*args, **kwargs)
            # -----------------------------------------------------------
            
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
inventario_bp = Blueprint('inventario', __name__)

# --- Rota GET /api/obras/<obra_id>/inventario/ (Sem alterações) ---
@inventario_bp.route('/obras/<int:obra_id>/inventario/', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_inventario_obra(obra_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        obra = Obras.query.get_or_404(obra_id)
        itens = InventarioItens.query.filter_by(obra_id=obra_id).order_by(InventarioItens.nome).all()
        return jsonify([item.to_dict() for item in itens]), 200
    except Exception as e:
        print(f"Erro ao buscar inventário da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao buscar inventário."}), 500

# --- Rota POST /api/obras/<obra_id>/inventario/ (Sem alterações) ---
@inventario_bp.route('/obras/<int:obra_id>/inventario/', methods=['POST', 'OPTIONS'])
@gestor_ou_admin_required()
def add_item_inventario(obra_id, **kwargs):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    current_user_id = get_jwt_identity()
    obra = Obras.query.get_or_404(obra_id)
    data = request.get_json()
    if not data or not data.get('nome') or not data.get('tipo'):
        return jsonify({"error": "Nome e Tipo são obrigatórios."}), 400
    try:
        quantidade = int(data.get('quantidade', 1))
        if quantidade <= 0:
            return jsonify({"error": "Quantidade deve ser positiva."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Formato de quantidade inválido."}), 400
    try:
        custo_unitario_str = data.get('custo_unitario')
        if custo_unitario_str:
             custo_unitario = float(custo_unitario_str.replace('.', '').replace(',', '.'))
        else:
            custo_unitario = None
        if custo_unitario is not None and custo_unitario < 0:
             return jsonify({"error": "Custo unitário não pode ser negativo."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Formato de custo unitário inválido."}), 400
    nome = data.get('nome')
    tipo = data.get('tipo')
    descricao = data.get('descricao')
    status_movimentacao = data.get('status_movimentacao', 'Em Estoque')
    try:
        novo_item = InventarioItens(
            obra_id=obra_id,
            tipo=tipo,
            nome=nome,
            descricao=descricao,
            quantidade=quantidade,
            custo_unitario=custo_unitario,
            status_movimentacao=status_movimentacao
        )
        db.session.add(novo_item)
        db.session.flush() 
        log_audit(
            current_user_id,
            'create',
            'InventarioItens',
            novo_item.id,
            {'obra_id': obra_id, 'nome': nome, 'tipo': tipo, 'quantidade': quantidade}
        )
        db.session.commit()
        return jsonify(novo_item.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar item ao inventário da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao salvar o item."}), 500


# --- ROTA COMBINADA (PUT / DELETE) (Sem alterações na lógica interna) ---
@inventario_bp.route('/inventario/<int:item_id>/', methods=['PUT', 'DELETE', 'OPTIONS'])
@gestor_ou_admin_required()
def manage_item_inventario(item_id, **kwargs):
    """
    Atualiza (PUT) ou remove (DELETE) um item de inventário existente.
    """
    
    # O decorator agora lida com o OPTIONS, mas deixamos aqui por segurança.
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    item = InventarioItens.query.get_or_404(item_id)
    current_user_id = get_jwt_identity()

    # --- LÓGICA PUT (ATUALIZAR) ---
    if request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados da requisição não encontrados."}), 400
        try:
            estado_anterior = item.to_dict()
            item.nome = data.get('nome', item.nome)
            item.tipo = data.get('tipo', item.tipo)
            item.descricao = data.get('descricao', item.descricao)
            item.status_movimentacao = data.get('status_movimentacao', item.status_movimentacao)
            if 'quantidade' in data:
                try:
                    item.quantidade = int(data.get('quantidade'))
                    if item.quantidade < 0:
                         return jsonify({"error": "Quantidade não pode ser negativa."}), 400
                except (ValueError, TypeError):
                    return jsonify({"error": "Formato de quantidade inválido."}), 400
            if 'custo_unitario' in data:
                 try:
                    custo_unitario_str = data.get('custo_unitario')
                    if custo_unitario_str:
                         item.custo_unitario = float(custo_unitario_str.replace('.', '').replace(',', '.'))
                    else:
                        item.custo_unitario = None
                    if item.custo_unitario is not None and item.custo_unitario < 0:
                         return jsonify({"error": "Custo unitário não pode ser negativo."}), 400
                 except (ValueError, TypeError):
                    return jsonify({"error": "Formato de custo unitário inválido."}), 400
            db.session.add(item)
            log_audit(
                current_user_id,
                'update',
                'InventarioItens',
                item.id,
                {'antes': estado_anterior, 'depois': item.to_dict()}
            )
            db.session.commit()
            return jsonify(item.to_dict()), 200
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao ATUALIZAR item de inventário {item_id}: {e}")
            return jsonify({"error": "Erro interno ao atualizar o item."}), 500

    # --- LÓGICA DELETE (REMOVER) ---
    if request.method == 'DELETE':
        try:
            log_audit(
                current_user_id,
                'delete',
                'InventarioItens',
                item.id,
                {'removido': item.to_dict()}
            )
            db.session.delete(item)
            db.session.commit()
            return '', 204
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao REMOVER item de inventário {item_id}: {e}")
            return jsonify({"error": "Erro interno ao remover o item."}), 500