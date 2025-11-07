from flask import Blueprint, jsonify, request, current_app
from ..models import Obras, ChecklistItem, AuditLog, User, ChecklistAnexo
from ..extensions import db
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename
import shutil
# --- NOVO: Importa as funções de segurança ---
from flask_jwt_extended import jwt_required, get_jwt_identity

# --- Helper para Log de Auditoria ---
def log_audit(user_id, action_type, resource_type, resource_id, details=None):
    """Cria uma entrada no log de auditoria."""
    try:
        log_entry = AuditLog(
            user_id=user_id, ### <-- Agora receberá o ID correto
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details
        )
        db.session.add(log_entry)
        # O commit será feito pela rota principal
    except Exception as e:
        print(f"ERRO CRÍTICO ao tentar criar log de auditoria: {e}")

# --- Constantes para Upload de Anexos ---
CHECKLIST_UPLOAD_FOLDER = 'uploads/checklist_pics'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Cria o Blueprint
checklist_bp = Blueprint('checklist', __name__)

# --- Rota GET /api/obras/<obra_id>/checklist/ ---
@checklist_bp.route('/obras/<int:obra_id>/checklist/', methods=['GET', 'OPTIONS'])
@jwt_required() ### <-- NOVO: Rota protegida
def get_checklist_obra(obra_id):
    """Busca todos os itens de checklist de uma obra específica."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    # TODO: Adicionar verificação de permissão (se o usuário pode ver esta obra)

    try:
        obra = Obras.query.get_or_404(obra_id)
        itens = ChecklistItem.query.filter_by(obra_id=obra_id).order_by(ChecklistItem.status.asc(), ChecklistItem.data_cadastro.desc()).all()
        return jsonify([item.to_dict() for item in itens]), 200
    except Exception as e:
        print(f"Erro ao buscar checklist da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao buscar checklist."}), 500

# --- Rota POST /api/obras/<obra_id>/checklist/ ---
@checklist_bp.route('/obras/<int:obra_id>/checklist/', methods=['POST', 'OPTIONS'])
@jwt_required() ### <-- NOVO: Rota protegida
def add_item_checklist(obra_id):
    """Adiciona um novo item ao checklist de uma obra."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    # --- NOVO: Obter o ID do usuário que está logado ---
    current_user_id = get_jwt_identity()
    # ----------------------------------------------------

    obra = Obras.query.get_or_404(obra_id)
    data = request.get_json()

    if not data or not data.get('titulo'):
        return jsonify({"error": "O Título é obrigatório."}), 400

    titulo = data.get('titulo')
    descricao = data.get('descricao')
    responsavel_user_id = data.get('responsavel_user_id')
    
    prazo_str = data.get('prazo')
    prazo = None
    if prazo_str:
        try:
            prazo = date.fromisoformat(prazo_str)
        except ValueError:
             return jsonify({"error": "Formato de data inválido para o prazo (use YYYY-MM-DD)."}), 400
             
    # REMOVIDO: criado_por_id = 1

    try:
        novo_item = ChecklistItem(
            obra_id=obra_id,
            titulo=titulo,
            descricao=descricao,
            responsavel_user_id=responsavel_user_id if responsavel_user_id else None,
            status='pendente',
            prazo=prazo
            # NOTA: O modelo 'ChecklistItem' não parece ter 'criado_por'.
            # Se tiver, adicione 'criado_por=current_user_id' aqui.
        )

        db.session.add(novo_item)
        db.session.flush() # Para obter o ID para o log

        log_audit(
            current_user_id, ### <-- NOVO: Usa o ID do usuário real
            'create',
            'ChecklistItem',
            novo_item.id,
            {'obra_id': obra_id, 'titulo': titulo, 'responsavel_id': responsavel_user_id, 'prazo': prazo_str}
        )

        db.session.commit()
        return jsonify(novo_item.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar item ao checklist da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao salvar o item."}), 500

# --- Rota PUT /api/checklist/<item_id>/ ---
@checklist_bp.route('/checklist/<int:item_id>/', methods=['PUT', 'OPTIONS'])
@jwt_required() ### <-- NOVO: Rota protegida
def update_item_checklist(item_id):
    """Atualiza o status ou outros dados de um item do checklist."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    # --- NOVO: Obter o ID do usuário que está logado ---
    current_user_id = get_jwt_identity()
    # ----------------------------------------------------
    
    item = ChecklistItem.query.get_or_404(item_id)
    data = request.get_json()
    # REMOVIDO: user_id = 1
    
    try:
        alteracoes = {}
        estado_anterior = item.to_dict() 
        estado_anterior.pop('status_display', None) 
        estado_anterior.pop('anexos', None) 

        # Atualiza Status
        if 'status' in data:
            novo_status = data.get('status')
            if novo_status not in ['pendente', 'feito']:
                return jsonify({"error": "Status inválido (deve ser 'pendente' ou 'feito')."}), 400
            
            if item.status != novo_status:
                item.status = novo_status
                alteracoes['status'] = novo_status
                if novo_status == 'feito':
                    item.data_conclusao = datetime.now()
                else:
                    item.data_conclusao = None
        
        # ... (lógica para atualizar outros campos permanece a mesma) ...
        if 'titulo' in data and data['titulo'] != item.titulo:
            item.titulo = data['titulo']
            alteracoes['titulo'] = item.titulo
            
        if 'descricao' in data and data['descricao'] != item.descricao:
            item.descricao = data['descricao']
            alteracoes['descricao'] = item.descricao

        if 'prazo' in data:
            novo_prazo_str = data.get('prazo')
            novo_prazo = None
            if novo_prazo_str:
                try:
                    novo_prazo = date.fromisoformat(novo_prazo_str)
                except ValueError:
                    return jsonify({"error": "Formato de data inválido para o prazo (use YYYY-MM-DD)."}), 400
            
            if novo_prazo != item.prazo:
                item.prazo = novo_prazo
                alteracoes['prazo'] = novo_prazo_str

        if 'responsavel_user_id' in data:
             novo_resp_id = data.get('responsavel_user_id')
             novo_resp_id_int = int(novo_resp_id) if novo_resp_id else None
             if novo_resp_id_int != item.responsavel_user_id:
                 item.responsavel_user_id = novo_resp_id_int
                 alteracoes['responsavel_user_id'] = item.responsavel_user_id
        # ... (fim da lógica de atualização) ...
        
        if alteracoes:
            log_audit(
                current_user_id, ### <-- NOVO: Usa o ID do usuário real
                'update',
                'ChecklistItem',
                item.id,
                {'antes': {k: estado_anterior[k] for k in alteracoes}, 
                 'depois': alteracoes}
            )

        db.session.commit()
        return jsonify(item.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar item de checklist {item_id}: {e}")
        return jsonify({"error": "Erro interno ao atualizar o item."}), 500

# --- Rota DELETE /api/checklist/<item_id>/ ---
@checklist_bp.route('/checklist/<int:item_id>/', methods=['DELETE', 'OPTIONS'])
@jwt_required() ### <-- NOVO: Rota protegida
def delete_item_checklist(item_id):
    """Remove um item do checklist e os seus anexos."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    # --- NOVO: Obter o ID do usuário que está logado ---
    current_user_id = get_jwt_identity()
    # ----------------------------------------------------

    item = ChecklistItem.query.get_or_404(item_id)
    # REMOVIDO: user_id = 1
    
    try:
        dados_removidos = item.to_dict() 
        ficheiros_a_remover = [anexo.filename for anexo in item.anexos]

        log_audit(
            current_user_id, ### <-- NOVO: Usa o ID do usuário real
            'delete',
            'ChecklistItem',
            item.id,
            {'removido': dados_removidos}
        )

        db.session.delete(item) 
        db.session.commit() 

        # Remove os ficheiros do disco APÓS o commit
        upload_path_full = os.path.join(current_app.instance_path, CHECKLIST_UPLOAD_FOLDER)
        for filename in ficheiros_a_remover:
            try:
                file_path = os.path.join(upload_path_full, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as file_e:
                print(f"Aviso: Não foi possível remover o ficheiro de anexo {filename}: {file_e}")

        return '', 204 
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover item de checklist {item_id}: {e}")
        return jsonify({"error": "Erro interno ao remover o item."}), 500

# --- Rota POST /api/checklist/<item_id>/anexo/ ---
@checklist_bp.route('/checklist/<int:item_id>/anexo/', methods=['POST', 'OPTIONS'])
@jwt_required() ### <-- NOVO: Rota protegida
def adicionar_anexo_checklist(item_id):
    """Adiciona um anexo (imagem) a um item do checklist."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
        
    # --- NOVO: Obter o ID do usuário que está logado ---
    current_user_id = get_jwt_identity()
    # ----------------------------------------------------
        
    item = ChecklistItem.query.get_or_404(item_id)
    # REMOVIDO: user_id = 1

    if len(item.anexos) >= 4:
         return jsonify({"error": "Limite de 4 anexos por tarefa atingido."}), 400

    if 'photo' not in request.files:
        return jsonify({"error": "Nenhum ficheiro 'photo' encontrado na requisição."}), 400
        
    foto_file = request.files['photo']
    
    if foto_file.filename == '':
        return jsonify({"error": "Nenhum ficheiro selecionado."}), 400

    if foto_file and allowed_file(foto_file.filename):
        try:
            filename = secure_filename(f"checklist_{item_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto_file.filename}")
            
            upload_path_full = os.path.join(current_app.instance_path, CHECKLIST_UPLOAD_FOLDER)
            os.makedirs(upload_path_full, exist_ok=True) 
            
            save_path = os.path.join(upload_path_full, filename)
            foto_file.save(save_path)

            novo_anexo = ChecklistAnexo(
                checklist_item_id=item_id,
                filename=filename
            )
            db.session.add(novo_anexo)
            db.session.flush() 
            
            log_audit(
                current_user_id, ### <-- NOVO: Usa o ID do usuário real
                'create_anexo',
                'ChecklistItem',
                item.id,
                {'anexo_id': novo_anexo.id, 'filename': filename}
            )
            
            db.session.commit()
            
            return jsonify(novo_anexo.to_dict()), 201

        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar anexo para checklist {item_id}: {e}")
            return jsonify({"error": "Erro interno ao salvar o anexo."}), 500
    else:
        return jsonify({"error": "Tipo de ficheiro não permitido (use .png, .jpg, .jpeg, .gif)."}), 400

# --- Rota DELETE /api/checklist/anexo/<anexo_id>/ ---
@checklist_bp.route('/checklist/anexo/<int:anexo_id>/', methods=['DELETE', 'OPTIONS'])
@jwt_required() ### <-- NOVO: Rota protegida
def remover_anexo_checklist(anexo_id):
    """Remove um anexo específico de um item do checklist."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    # --- NOVO: Obter o ID do usuário que está logado ---
    current_user_id = get_jwt_identity()
    # ----------------------------------------------------
    
    anexo = ChecklistAnexo.query.get_or_404(anexo_id)
    # REMOVIDO: user_id = 1
    
    try:
        filename = anexo.filename
        item_id = anexo.checklist_item_id
        
        log_audit(
            current_user_id, ### <-- NOVO: Usa o ID do usuário real
            'delete_anexo',
            'ChecklistItem',
            item_id,
            {'anexo_id': anexo.id, 'filename': filename}
        )

        db.session.delete(anexo)
        db.session.commit()

        try:
            file_path = os.path.join(current_app.instance_path, CHECKLIST_UPLOAD_FOLDER, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as file_e:
            print(f"Aviso: Não foi possível remover o ficheiro de anexo {filename}: {file_e}")

        return '', 204

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover anexo {anexo_id}: {e}")
        return jsonify({"error": "Erro interno ao remover o anexo."}), 500