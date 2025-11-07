import os
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from ..models import Obras, Documentos, AuditLog, User
from ..extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
from flask_jwt_extended import jwt_required, get_jwt_identity

# --- Constantes ---
DOCUMENTOS_UPLOAD_FOLDER = 'uploads/documentos_obra' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'dwg', 'dxf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Helper para Log de Auditoria ---
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
documentos_bp = Blueprint('documentos', __name__)

# --- Rota GET (Sem alterações) ---
@documentos_bp.route('/obras/<int:obra_id>/documentos/', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_documentos_obra(obra_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200
    try:
        obra = Obras.query.get_or_404(obra_id)
        documentos = Documentos.query.filter_by(obra_id=obra_id).order_by(Documentos.uploaded_at.desc()).all()
        return jsonify([doc.to_dict() for doc in documentos]), 200
    except Exception as e:
        print(f"Erro ao buscar documentos da obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao buscar documentos."}), 500

# --- Rota POST (CORRIGIDA) ---
@documentos_bp.route('/obras/<int:obra_id>/documentos/', methods=['POST', 'OPTIONS'])
@jwt_required()
def upload_documento_obra(obra_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    current_user_id = get_jwt_identity()
    obra = Obras.query.get_or_404(obra_id)
    
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum ficheiro 'file' encontrado na requisição."}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Nenhum ficheiro selecionado."}), 400

    # NOTA: O 'allowed_file' JÁ protege contra arquivos sem extensão
    # O problema é que o código ABAIXO não esperava por isso.
    if not allowed_file(file.filename):
        return jsonify({"error": "Tipo de ficheiro não permitido."}), 400
    
    try:
        original_filename = secure_filename(file.filename)
        
        # --- INÍCIO DA CORREÇÃO ---
        # Corrige o erro 'list index out of range'
        split_filename = original_filename.rsplit('.', 1)
        
        # split_filename será ['nome', 'ext'] ou apenas ['nome']
        if len(split_filename) == 2:
            extensao = split_filename[1].lower()
            unique_filename = f"{uuid.uuid4()}.{extensao}"
        else:
            # Caso o arquivo não tenha extensão (ex: 'meuarquivo')
            extensao = '' # Sem extensão
            unique_filename = str(uuid.uuid4())
        
        # Usa a extensão como 'tipo' se o 'tipo' não for enviado pelo form
        tipo_documento = request.form.get('tipo', extensao)
        # --- FIM DA CORREÇÃO ---
        
        upload_path_full = os.path.join(current_app.instance_path, DOCUMENTOS_UPLOAD_FOLDER)
        os.makedirs(upload_path_full, exist_ok=True) 
        
        save_path = os.path.join(upload_path_full, unique_filename)
        file.save(save_path)

        novo_documento = Documentos(
            obra_id=obra_id,
            filename=original_filename,
            filepath=unique_filename,
            tipo=tipo_documento, # <-- Usa a variável corrigida
            visibilidade=request.form.get('visibilidade', 'todos'),
            uploaded_by=current_user_id
        )
        db.session.add(novo_documento)
        
        db.session.flush()
        
        log_audit(
            current_user_id,
            'upload_documento',
            'Documentos',
            novo_documento.id,
            {'obra_id': obra_id, 'filename': original_filename}
        )
        
        db.session.commit()
        
        return jsonify(novo_documento.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        # Esta é a linha que você viu no seu log
        print(f"Erro ao salvar documento para obra {obra_id}: {e}")
        return jsonify({"error": "Erro interno ao salvar o documento."}), 500

# --- Rota DELETE (Sem alterações) ---
@documentos_bp.route('/documentos/<int:documento_id>/', methods=['DELETE', 'OPTIONS'])
@jwt_required() 
def delete_documento(documento_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'Preflight OK'}), 200

    current_user_id = get_jwt_identity()
    doc = Documentos.query.get_or_404(documento_id)
    
    try:
        filename = doc.filepath
        obra_id = doc.obra_id
        original_filename = doc.filename
        
        log_audit(
            current_user_id,
            'delete_documento',
            'Documentos',
            doc.id,
            {'obra_id': obra_id, 'filename': original_filename}
        )

        db.session.delete(doc)
        db.session.commit()

        try:
            file_path = os.path.join(current_app.instance_path, DOCUMENTOS_UPLOAD_FOLDER, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as file_e:
            print(f"Aviso: Não foi possível remover o ficheiro {filename}: {file_e}")

        return '', 204

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover documento {documento_id}: {e}")
        return jsonify({"error": "Erro interno ao remover o documento."}), 500