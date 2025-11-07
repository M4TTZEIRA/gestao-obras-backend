# Importa as funções e objetos necessários
from backend import create_app, db
from backend.models import Role, User

def seed_data():
    """Função principal para popular o banco de dados."""
    
    # --- 1. Criação dos Cargos (Roles) ---
    print("Iniciando o processo de seeding...")
    
    roles_to_create = ['Administrador', 'Gestor', 'Prestador']
    
    for role_name in roles_to_create:
        # Verifica se a role já existe para não criar duplicatas
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            new_role = Role(name=role_name)
            db.session.add(new_role)
            print(f"Cargo '{role_name}' criado.")
        else:
            print(f"Cargo '{role_name}' já existe.")
            
    # Comita as roles para que possamos usá-las para o usuário
    try:
        db.session.commit()
        print("Cargos salvos no banco de dados.")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar cargos: {e}")
        return # Para a execução se não conseguir criar as roles

    # --- 2. Criação do Usuário Administrador ---
    
    # Verifica se o usuário admin já existe
    admin_user = User.query.filter_by(username='admin').first()
    
    if not admin_user:
        print("Criando usuário administrador...")
        
        # Pega a role 'Administrador' que acabamos de criar
        admin_role = Role.query.filter_by(name='Administrador').first()
        
        if admin_role:
            # **ATENÇÃO: Altere a senha para uma senha segura!**
            new_admin = User(
                username='admin',
                email='admin@seuemail.com',
                nome='Administrador do Sistema',
                role_id=admin_role.id
            )
            # Define a senha usando o método seguro que já existe no seu modelo User
            new_admin.set_password('admin123') 
            
            db.session.add(new_admin)
            
            try:
                db.session.commit()
                print("Usuário administrador criado com sucesso!")
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao criar usuário administrador: {e}")
        else:
            print("ERRO CRÍTICO: Não foi possível encontrar a role 'Administrador' para criar o usuário.")
            
    else:
        print("Usuário 'admin' já existe.")
        
    print("Processo de seeding concluído.")


# --- Bloco de Execução ---
# Este código é executado quando você roda `python -m backend.seed`
if __name__ == '__main__':
    # Cria a aplicação Flask para ter o contexto do banco de dados
    app = create_app()
    
    # O `with app.app_context()` garante que a conexão com o DB está ativa
    with app.app_context():
        seed_data()