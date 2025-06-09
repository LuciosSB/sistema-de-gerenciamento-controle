from db_setup import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    dados = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    tipo_usuario = db.Column(db.String(50), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        permissions_map = {
            'almoxarifado': ['cadastro_usuario', 'atualizar_produto', 'listar_produtos', 'saida_produto', 'gerenciar_solicitacoes'],
            'usuario_padrao': ['gerenciar_solicitacoes', 'cadastrar_item', 'listar_itens', 'atualizar_item'],
            'usuario_solicitante': ['portal_solicitacoes','gerenciar_solicitacoes'],
            'admin':['cadastro_usuario', 'listar_usuarios', 'atualizar_usuario', 'deletar_usuario', 'gerenciar_solicitacoes','cadastrar_produto', 'atualizar_produto', 'listar_produtos', 'saida_produto','cadastrar_item', 'listar_itens', 'atualizar_item']
        }
        return permission in permissions_map.get(self.tipo_usuario, [])
    
    def __repr__(self):
        return f'<Usuario {self.username}>'

class Produto(db.Model):
    __tablename__ = 'produto'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    
    # NOVO CAMPO para diferenciar itens que voltam dos que não voltam.
    # 'consumivel' para o que não volta (ex: parafusos, fita isolante).
    # 'retornavel' para o que deve ser devolvido (ex: furadeira, multímetro).
    tipo_item = db.Column(db.String(50), nullable=False, default='consumivel')
    
    def __repr__(self):
        return f'<Produto {self.nome}>'

class Setor(db.Model):
    __tablename__ = 'setor'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    
    def __repr__(self):
        return f'<Setor {self.nome}>'

class Solicitacao(db.Model):
    __tablename__ = 'solicitacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Campos existentes que serão mantidos
    nome_solicitante = db.Column(db.String(255), nullable=False)
    setor = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='pendente')  # Ex: pendente, aprovada, rejeitada, concluida
    data_solicitacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    # --- CAMPOS NOVOS PARA O CHAMADO DE MANUTENÇÃO ---
    titulo = db.Column(db.String(200), nullable=False, default="Título não informado")
    categoria = db.Column(db.String(100), nullable=False, default="Geral")
    urgencia = db.Column(db.String(50), nullable=False, default='baixa') # Ex: baixa, media, alta
    motivo_rejeicao = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<Solicitacao {self.id}: {self.titulo} - {self.status}>'