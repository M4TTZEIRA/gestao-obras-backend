from flask import Blueprint, jsonify, request
from ..models import Obras, FinanceiroTransacoes, User, InventarioItens, ChecklistItem, Documentos
from ..extensions import db
from sqlalchemy.sql import func
from datetime import datetime, date
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from functools import wraps

# --- Decorator (Sem alterações) ---
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

# --- Helper (Sem alterações) ---
def format_cashflow_data(query_results):
    data_map = {}
    for mes, tipo, total in query_results:
        if mes not in data_map:
            data_map[mes] = {'entrada': 0.0, 'saida': 0.0}
        total_float = float(total or 0.0)
        if tipo == 'entrada':
            data_map[mes]['entrada'] = total_float
        elif tipo == 'saida':
            data_map[mes]['saida'] = total_float
    sorted_labels = sorted(data_map.keys())
    entradas_data = []
    saidas_data = []
    for label in sorted_labels:
        entradas_data.append(data_map[label]['entrada'])
        saidas_data.append(data_map[label]['saida'])
    return {
        'labels': sorted_labels,
        'datasets': [
            {'label': 'Entradas (R$)', 'data': entradas_data, 'backgroundColor': 'rgba(34, 197, 94, 0.6)', 'borderColor': 'rgba(34, 197, 94, 1)', 'borderWidth': 1},
            {'label': 'Saídas (R$)', 'data': saidas_data, 'backgroundColor': 'rgba(239, 68, 68, 0.6)', 'borderColor': 'rgba(239, 68, 68, 1)', 'borderWidth': 1}
        ]
    }

# --- Blueprint ---
reports_bp = Blueprint('reports', __name__)

# --- Rota KPIs (Sem alterações) ---
@reports_bp.route('/reports/kpis/', methods=['GET', 'OPTIONS'])
@gestor_ou_admin_required()
def get_global_kpis(**kwargs):
    # ... (código existente sem alterações) ...
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        total_obras = db.session.query(func.count(Obras.id)).filter(Obras.is_stock_default == False).scalar() or 0 # Ignora o estoque
        obras_ativas = db.session.query(func.count(Obras.id)).filter(Obras.status == 'Em Andamento', Obras.is_stock_default == False).scalar() or 0
        total_orcamento_atual = db.session.query(func.sum(Obras.orcamento_atual)).filter(Obras.is_stock_default == False).scalar() or 0.0
        total_custos = db.session.query(func.sum(FinanceiroTransacoes.valor)).join(Obras).filter(
            FinanceiroTransacoes.tipo == 'saida',
            FinanceiroTransacoes.status == 'ativo',
            Obras.is_stock_default == False
        ).scalar() or 0.0
        total_receitas = db.session.query(func.sum(FinanceiroTransacoes.valor)).join(Obras).filter(
            FinanceiroTransacoes.tipo == 'entrada',
            FinanceiroTransacoes.status == 'ativo',
            Obras.is_stock_default == False
        ).scalar() or 0.0
        kpis = {
            'total_obras': total_obras,
            'obras_ativas': obras_ativas,
            'obras_concluidas': db.session.query(func.count(Obras.id)).filter(Obras.status == 'Concluída', Obras.is_stock_default == False).scalar() or 0,
            'total_orcamento_atual': str(total_orcamento_atual),
            'total_custos': str(total_custos),
            'total_receitas': str(total_receitas),
        }
        return jsonify(kpis), 200
    except Exception as e:
        print(f"Erro ao calcular KPIs globais: {e}")
        return jsonify({"error": "Erro interno ao calcular os relatórios."}), 500

# --- Rota Cashflow (ATUALIZADA) ---
@reports_bp.route('/reports/cashflow/', methods=['GET', 'OPTIONS'])
@gestor_ou_admin_required()
def get_cashflow_report(**kwargs):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        periodo = request.args.get('periodo', 'mensal')
        dialect = db.engine.dialect.name
        if dialect == 'postgresql':
            grouping_format = 'YYYY-WW' if periodo == 'semanal' else 'YYYY-MM'
            grouping_expression = func.to_char(FinanceiroTransacoes.criado_em, grouping_format)
        else:
            grouping_format = '%Y-%W' if periodo == 'semanal' else '%Y-%m'
            grouping_expression = func.strftime(grouping_format, FinanceiroTransacoes.criado_em)
        
        cashflow_data = db.session.query(
            grouping_expression.label('periodo_label'),
            FinanceiroTransacoes.tipo,
            func.sum(FinanceiroTransacoes.valor).label('total')
        ).join(Obras).filter( # <-- JOIN com Obras
            FinanceiroTransacoes.status == 'ativo',
            Obras.is_stock_default == False # <-- Ignora o estoque
        ).group_by(
            'periodo_label', FinanceiroTransacoes.tipo
        ).order_by(
            'periodo_label'
        ).all()
        formatted_data = format_cashflow_data(cashflow_data)
        return jsonify(formatted_data), 200
    except Exception as e:
        print(f"Erro ao calcular fluxo de caixa: {e}")
        return jsonify({"error": "Erro interno ao calcular o fluxo de caixa."}), 500


# --- Rota Inventário Global (ATUALIZADA) ---
@reports_bp.route('/reports/global-inventory/', methods=['GET', 'OPTIONS'])
@gestor_ou_admin_required()
def get_global_inventory(**kwargs):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        # Busca TODOS os itens e suas obras
        all_items_query = db.session.query(
            InventarioItens,
            Obras.nome.label('obra_nome'),
            Obras.is_stock_default # <-- Pega a nova flag
        ).join(
            Obras, InventarioItens.obra_id == Obras.id
        ).order_by(
            Obras.nome.asc(), InventarioItens.nome.asc()
        ).all()
        
        # Separa as listas
        stock_items = []
        obra_items = []
        
        for item, obra_nome, is_stock in all_items_query:
            item_dict = item.to_dict()
            item_dict['obra_nome'] = obra_nome 
            
            if is_stock:
                stock_items.append(item_dict)
            else:
                obra_items.append(item_dict)
            
        return jsonify({
            'stock_items': stock_items,
            'obra_items': obra_items
        }), 200

    except Exception as e:
        print(f"Erro ao calcular inventário global: {e}")
        return jsonify({"error": "Erro interno ao calcular o inventário."}), 500


# --- Rota Checklist Global (Sem alterações) ---
@reports_bp.route('/reports/global-checklist/', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_global_checklist(**kwargs):
    # ... (código existente sem alterações) ...
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        current_user_id = get_jwt_identity()
        today = date.today()
        my_tasks_query = db.session.query(
            ChecklistItem,
            Obras.nome.label('obra_nome')
        ).join(Obras).filter(
            ChecklistItem.responsavel_user_id == current_user_id,
            ChecklistItem.status == 'pendente',
            Obras.is_stock_default == False # Ignora o estoque
        ).order_by(
            ChecklistItem.prazo.asc()
        ).all()
        overdue_tasks_query = db.session.query(
            ChecklistItem,
            Obras.nome.label('obra_nome')
        ).join(Obras).filter(
            ChecklistItem.status == 'pendente',
            ChecklistItem.prazo != None,
            ChecklistItem.prazo < today,
            Obras.is_stock_default == False # Ignora o estoque
        ).order_by(
            ChecklistItem.prazo.asc()
        ).all()
        def format_task(task_data):
            task, obra_nome = task_data
            task_dict = task.to_dict()
            task_dict['obra_nome'] = obra_nome
            return task_dict
        my_tasks = [format_task(t) for t in my_tasks_query]
        overdue_tasks = [format_task(t) for t in overdue_tasks_query]
        return jsonify({
            'my_tasks': my_tasks,
            'overdue_tasks': overdue_tasks
        }), 200
    except Exception as e:
        print(f"Erro ao calcular checklist global: {e}")
        return jsonify({"error": "Erro interno ao calcular o checklist."}), 500

# --- Rota Documentos Globais (ATUALIZADA) ---
@reports_bp.route('/reports/global-documents/', methods=['GET', 'OPTIONS'])
@gestor_ou_admin_required()
def get_global_documents(**kwargs):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        documents_data = db.session.query(
            Documentos,
            Obras.nome.label('obra_nome')
        ).join(Obras).filter(
            Obras.is_stock_default == False # <-- Ignora o estoque
        ).order_by(
            Obras.nome.asc(), Documentos.uploaded_at.desc()
        ).all()
        results = []
        for doc, obra_nome in documents_data:
            doc_dict = doc.to_dict()
            doc_dict['obra_nome'] = obra_nome
            results.append(doc_dict)
        return jsonify(results), 200
    except Exception as e:
        print(f"Erro ao calcular documentos globais: {e}")
        return jsonify({"error": "Erro interno ao calcular os documentos."}), 500