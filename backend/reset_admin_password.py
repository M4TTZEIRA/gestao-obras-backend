from backend import create_app, db
from backend.models import User

# Cria uma instância da aplicação para ter o contexto do banco de dados
app = create_app()

with app.app_context():
    # Encontra o usuário 'admin'
    user = User.query.filter_by(username='admin').first()

    if user:
        print("--- SCRIPT DE RESET ---")
        print("Usuário 'admin' encontrado. Resetando a senha...")

        # **ATENÇÃO: MUDE A SENHA AQUI**
        user.set_password('novaSenhaSegura456') 

        db.session.commit()
        print("Senha do usuário 'admin' foi resetada com sucesso!")
        print("--- SCRIPT CONCLUÍDO ---")
    else:
        print("--- SCRIPT DE RESET ---")
        print("Erro: Usuário 'admin' não encontrado no banco de dados.")
        print("--- SCRIPT CONCLUÍDO ---")
        