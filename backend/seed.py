from backend import create_app, db
from backend.models import Role, User, Obras # <-- Adiciona Obras

def seed_data():
    """Função principal para popular o banco de dados."""
    
    # --- 1. Criação dos Cargos (Roles) ---
    print("Iniciando o processo de seeding...")
    
    roles_to_create = ['Administrador', 'Gestor', 'Prestador']
    
    for role_name in roles_to_create:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            new_role = Role(name=role_name)
            db.session.add(new_role)
            print(f"Cargo '{role_name}' criado.")
        else:
            print(f"Cargo '{role_name}' já existe.")
            
    try:
        db.session.commit()
        print("Cargos salvos no banco de dados.")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar cargos: {e}")
        return 

    # --- 2. Criação do Usuário Administrador ---
    admin_user = User.query.filter_by(username='admin').first()
    
    if not admin_user:
        print("Criando usuário administrador...")
        admin_role = Role.query.filter_by(name='Administrador').first()
        
        if admin_role:
            new_admin = User(
                username='admin',
                email='admin@seuemail.com',
                nome='Administrador do Sistema',
                role_id=admin_role.id
            )
            new_admin.set_password('admin123') 
            new_admin.must_change_password = False # Libera o admin
            db.session.add(new_admin)
            
            try:
                db.session.commit()
                print("Usuário administrador criado com sucesso!")
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao criar usuário administrador: {e}")
        else:
            print("ERRO CRÍTICO: Não foi possível encontrar a role 'Administrador'.")
    else:
        # Garante que o usuário admin existente não esteja bloqueado
        if admin_user.must_change_password == True:
            admin_user.must_change_password = False
            db.session.add(admin_user)
            db.session.commit()
            print("Usuário 'admin' já existe e foi desbloqueado (must_change_password=False).")
        else:
            print("Usuário 'admin' já existe.")
            
    
    # --- 3. (NOVO) Cria a Obra "Estoque Central" ---
    stock_obra = Obras.query.filter_by(is_stock_default=True).first()
    
    if not stock_obra:
        print("Criando obra 'Estoque Central'...")
        
        # Pega o ID do admin que acabamos de verificar/criar
        admin_user = User.query.filter_by(username='admin').first()
        admin_id = admin_user.id if admin_user else None
        
        nova_obra_estoque = Obras(
            nome='Estoque Central da Empresa',
            endereco='Sede da Empresa',
            proprietario='Empresa',
            orcamento_inicial=0,
            orcamento_atual=0,
            status='Ativo', # Status especial
            criado_por=admin_id,
            is_stock_default=True # <-- A MARCAÇÃO ESPECIAL
        )
        db.session.add(nova_obra_estoque)
        
        try:
            db.session.commit()
            print("Obra 'Estoque Central' criada com sucesso!")
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar a obra 'Estoque Central': {e}")
    else:
        print("A obra 'Estoque Central' já existe.")

    print("Processo de seeding concluído.")


# --- Bloco de Execução ---
if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed_data()