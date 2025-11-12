from .extensions import db, bcrypt
from datetime import datetime, date # Importa date

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=True)
    rg = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    foto_path = db.Column(db.String(255), nullable=True) 
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False, default=3) 
    must_change_password = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    role = db.relationship('Role')
    
    # Relações de "quem criou" (para Auditoria e Histórico)
    obras_criadas = db.relationship('Obras', foreign_keys='Obras.criado_por', back_populates='criador_user')
    transacoes_criadas = db.relationship('FinanceiroTransacoes', foreign_keys='FinanceiroTransacoes.criado_por', back_populates='criador')
    transacoes_canceladas = db.relationship('FinanceiroTransacoes', foreign_keys='FinanceiroTransacoes.cancelado_por', back_populates='cancelador')
    documentos_enviados = db.relationship('Documentos', foreign_keys='Documentos.uploaded_by', back_populates='uploader')
    tarefas_atribuidas = db.relationship('ChecklistItem', foreign_keys='ChecklistItem.responsavel_user_id', back_populates='responsavel')
    logs_de_auditoria = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', back_populates='user')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self, include_details=False):
        foto_url = f'/api/uploads/profile_pics/{self.foto_path}' if self.foto_path else None
        data = {
            'id': self.id,
            'username': self.username,
            'nome': self.nome,
            'email': self.email,
            'telefone': self.telefone,
            'role': self.role.name if self.role else None,
            'foto_path': foto_url, 
            'must_change_password': self.must_change_password
        }
        if include_details:
             data['cpf'] = self.cpf
             data['rg'] = self.rg
        return data

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    permissions = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'permissions': self.permissions
        }


class Obras(db.Model):
    __tablename__ = 'obras'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    endereco = db.Column(db.String(255), nullable=True)
    proprietario = db.Column(db.String(120), nullable=True)
    orcamento_inicial = db.Column(db.Numeric(10, 2), nullable=True, default=0.0)
    orcamento_atual = db.Column(db.Numeric(10, 2), nullable=True, default=0.0)
    status = db.Column(db.String(50), default='Em Andamento')
    criado_por = db.Column(db.Integer, db.ForeignKey('users.id'))
    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # --- ESTE É O CAMPO QUE FALTAVA ---
    is_stock_default = db.Column(db.Boolean, nullable=False, default=False)
    # ---------------------------------

    criador_user = db.relationship('User', foreign_keys=[criado_por], back_populates='obras_criadas')
    funcionarios = db.relationship('ObraFuncionarios', back_populates='obra', cascade="all, delete-orphan")
    transacoes = db.relationship('FinanceiroTransacoes', back_populates='obra', cascade="all, delete-orphan")
    inventario = db.relationship('InventarioItens', back_populates='obra', cascade="all, delete-orphan")
    checklist_itens = db.relationship('ChecklistItem', back_populates='obra', cascade="all, delete-orphan")
    documentos = db.relationship('Documentos', back_populates='obra', cascade="all, delete-orphan")


    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'endereco': self.endereco,
            'proprietario': self.proprietario,
            'orcamento_inicial': str(self.orcamento_inicial) if self.orcamento_inicial is not None else "0.00",
            'orcamento_atual': str(self.orcamento_atual) if self.orcamento_atual is not None else "0.00",
            'status': self.status,
            'criado_por': self.criado_por,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
            'is_stock_default': self.is_stock_default # <-- ADICIONADO AO DICIONÁRIO
        }

class ObraFuncionarios(db.Model):
    __tablename__ = 'obra_funcionarios'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cargo = db.Column(db.String(100), nullable=True)
    salario = db.Column(db.Numeric(10, 2), nullable=True)
    status_pagamento = db.Column(db.String(50), default='Pendente')
    prazo_limite = db.Column(db.Date, nullable=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    ultima_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    nome_nao_cadastrado = db.Column(db.String(120), nullable=True)
    cpf_nao_cadastrado = db.Column(db.String(14), nullable=True)
    foto_path_nao_cadastrado = db.Column(db.String(255), nullable=True)

    user = db.relationship('User')
    obra = db.relationship('Obras', back_populates='funcionarios')

    def calculate_status_pagamento(self):
        current_status = self.status_pagamento
        if current_status == 'Pago':
            return 'Pago'
        if self.prazo_limite and self.prazo_limite < date.today():
            return 'Atrasado'
        return current_status

    def to_dict(self):
        user_info = {}
        foto_a_usar = None
        if self.user_id:
            if self.user:
                user_info = {
                    "id_user": self.user.id,
                    "nome": self.user.nome,
                    "email": self.user.email,
                    "cpf": self.user.cpf,
                }
                foto_a_usar = f'/api/uploads/profile_pics/{self.user.foto_path}' if self.user.foto_path else None
            else:
                 user_info = {"id_user": self.user_id, "nome": "Erro ao carregar usuário", "email": None, "cpf": None}
        else:
            user_info = {
                "id_user": None,
                "nome": self.nome_nao_cadastrado,
                "email": None,
                "cpf": self.cpf_nao_cadastrado,
            }
            foto_a_usar = f'/api/uploads/profile_pics/{self.foto_path_nao_cadastrado}' if self.foto_path_nao_cadastrado else None
        user_info["foto_path"] = foto_a_usar 
        return {
            "id_vinculo": self.id,
            "obra_id": self.obra_id,
            "user": user_info,
            "cargo": self.cargo,
            "salario": str(self.salario) if self.salario is not None else "0.00",
            "status_pagamento": self.calculate_status_pagamento(),
            "prazo_limite": self.prazo_limite.isoformat() if self.prazo_limite else None,
            "data_cadastro": self.data_cadastro.isoformat() if self.data_cadastro else None,
            "ultima_atualizacao": self.ultima_atualizacao.isoformat() if self.ultima_atualizacao else None,
        }


class FinanceiroTransacoes(db.Model):
    __tablename__ = 'financeiro_transacoes'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # 'entrada', 'saida'
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    criado_por = db.Column(db.Integer, db.ForeignKey('users.id'))
    criado_em = db.Column(db.DateTime, default=datetime.now)
    atualizado_em = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    status = db.Column(db.String(50), nullable=False, default='ativo')
    cancelado_por = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cancelado_em = db.Column(db.DateTime, nullable=True)
    motivo_cancelamento = db.Column(db.Text, nullable=True)
    obra = db.relationship('Obras', back_populates='transacoes')
    criador = db.relationship('User', foreign_keys=[criado_por], back_populates='transacoes_criadas')
    cancelador = db.relationship('User', foreign_keys=[cancelado_por], back_populates='transacoes_canceladas')

    def to_dict(self):
        return {
            'id': self.id,
            'obra_id': self.obra_id,
            'tipo': self.tipo,
            'valor': str(self.valor) if self.valor is not None else "0.00",
            'descricao': self.descricao,
            'criado_por_nome': self.criador.nome if self.criador else "Sistema",
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
            'status': self.status,
            'cancelado_por_nome': self.cancelador.nome if self.cancelador else None,
            'cancelado_em': self.cancelado_em.isoformat() if self.cancelado_em else None,
            'motivo_cancelamento': self.motivo_cancelamento
        }


class InventarioItens(db.Model):
    __tablename__ = 'inventario_itens'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    tipo = db.Column(db.String(50)) 
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    quantidade = db.Column(db.Integer, default=1)
    custo_unitario = db.Column(db.Numeric(10, 2), nullable=True)
    status_movimentacao = db.Column(db.String(50), default='Em Estoque') 
    criado_em = db.Column(db.DateTime, default=datetime.now)

    obra = db.relationship('Obras', back_populates='inventario')

    def to_dict(self):
        return {
            'id': self.id,
            'obra_id': self.obra_id,
            'tipo': self.tipo,
            'nome': self.nome,
            'descricao': self.descricao,
            'quantidade': self.quantidade,
            'custo_unitario': str(self.custo_unitario) if self.custo_unitario is not None else "0.00",
            'status_movimentacao': self.status_movimentacao,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
        }

class PontoRegistros(db.Model):
    __tablename__ = 'ponto_registros'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    evento = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

class Documentos(db.Model):
    __tablename__ = 'documentos'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True) 
    filename = db.Column(db.String(255), nullable=False) 
    filepath = db.Column(db.String(255), nullable=False) 
    tipo = db.Column(db.String(50)) 
    visibilidade = db.Column(db.String(50), default='todos') 
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.now)

    obra = db.relationship('Obras', back_populates='documentos')
    uploader = db.relationship('User', foreign_keys=[uploaded_by], back_populates='documentos_enviados')

    def to_dict(self):
        return {
            'id': self.id,
            'obra_id': self.obra_id,
            'filename': self.filename, 
            'filepath_url': f'/api/uploads/documentos_obra/{self.filepath}', 
            'tipo': self.tipo,
            'visibilidade': self.visibilidade,
            'uploaded_by_nome': self.uploader.nome if self.uploader else "Sistema",
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
        }

class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    responsavel_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(50), default='pendente') 
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    prazo = db.Column(db.Date, nullable=True) 

    responsavel = db.relationship('User', foreign_keys=[responsavel_user_id], back_populates='tarefas_atribuidas')
    obra = db.relationship('Obras', back_populates='checklist_itens')
    anexos = db.relationship('ChecklistAnexo', back_populates='checklist_item', cascade="all, delete-orphan")

    def calculate_status_display(self):
        if self.status == 'feito':
            return 'Concluído'
        if self.prazo and self.prazo < date.today():
            return 'Atrasado'
        return 'Em dia' 

    def to_dict(self):
        return {
            'id': self.id,
            'obra_id': self.obra_id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'responsavel_user_id': self.responsavel_user_id,
            'responsavel_nome': self.responsavel.nome if self.responsavel else None,
            'status': self.status, 
            'status_display': self.calculate_status_display(), 
            'data_cadastro': self.data_cadastro.isoformat() if self.data_cadastro else None,
            'data_conclusao': self.data_conclusao.isoformat() if self.data_conclusao else None,
            'prazo': self.prazo.isoformat() if self.prazo else None, 
            'anexos': [anexo.to_dict() for anexo in self.anexos] 
        }

class ChecklistAnexo(db.Model):
    __tablename__ = 'checklist_anexos'
    id = db.Column(db.Integer, primary_key=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey('checklist_items.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False) 
    uploaded_at = db.Column(db.DateTime, default=datetime.now)
    
    # --- ESTA É A LINHA CORRIGIDA ---
    checklist_item = db.relationship('ChecklistItem', back_populates='anexos')

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'url': f'/api/uploads/checklist_pics/{self.filename}', 
            'uploaded_at': self.uploaded_at.isoformat()
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)
    resource_type = db.Column(db.String(100), nullable=True)
    resource_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', foreign_keys=[user_id], back_populates='logs_de_auditoria')