from backend import create_app, db

# Remova as importações dos modelos daqui de cima
# app = create_app() DEVE ser chamado antes de importar os modelos

app = create_app()

@app.shell_context_processor
def make_shell_context():
    # Importe os modelos AQUI DENTRO
    from backend.models import (
        User, Role, Obra, ObraFuncionario, FinanceiroTransacao, 
        InventarioItem, PontoRegistro, Documento, ChecklistItem, AuditLog
    )
    
    return {
        'db': db,
        'User': User,
        'Role': Role,
        'Obra': Obra,
        'ObraFuncionario': ObraFuncionario,
        'FinanceiroTransacao': FinanceiroTransacao,
        'InventarioItem': InventarioItem,
        'PontoRegistro': PontoRegistro,
        'Documento': Documento,
        'ChecklistItem': ChecklistItem,
        'AuditLog': AuditLog
    }

if __name__ == '__main__':
    app.run()

# ... (todo o código do run.py) ...

# FORÇAR ATUALIZAÇÃO DO DEPLOY