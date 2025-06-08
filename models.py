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
    tipo_usuario = db.Column(db.String(50), nullable=False)  # 'almoxarifado', 'eletrica', 'solicitante'
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
    nome_solicitante = db.Column(db.String(255), nullable=False)
    setor = db.Column(db.String(255), nullable=False)
    nome_item = db.Column(db.String(255), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='pendente')  # pendente, aprovada, rejeitada, entregue
    data_solicitacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Solicitacao {self.id}: {self.nome_item} - {self.status}>'