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
            'admin': [
                'gerenciar_solicitacoes', 'dashboard', 'cadastrar_produto', 'listar_produtos', 
                'atualizar_produto', 'saida_produto', 'cadastro_usuario', 'atualizar',
                'listar_usuarios', 'atualizar_cadastro', 'excluir_usuario', 'historico', 'portal_solocitacoes', 
                'gerenciar_solicitacoes', 'listar_solicitacoes'
            ],
            'manutencao': [
                'gerenciar_solicitacoes', 'listar_produtos', 'portal_solocitacoes'
            ],
            'usuario_gerenciador': [
                'cadastrar_produto', 'listar_produtos',
                'atualizar_produto', 'saida_produto', 'listar_solicitacoes', 'historico',
                'portal_solocitacoes', 'gerenciar_solicitacoes','dashboard'
            ]
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
    nome_solicitante = db.Column(db.String(255), nullable=False)
    setor = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='pendente')
    data_solicitacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    titulo = db.Column(db.String(200), nullable=False, default="Título não informado")
    categoria = db.Column(db.String(100), nullable=False, default="Geral")
    urgencia = db.Column(db.String(50), nullable=False, default='baixa')
    motivo_rejeicao = db.Column(db.Text, nullable=True)

    def get_ultimo_comentario(self):
        # Este método busca e retorna o último comentário associado a este chamado
        return self.comentarios.order_by(Comentario.id.desc()).first()
    
    def __repr__(self):
        return f'<Solicitacao {self.id}: {self.titulo} - {self.status}>'


class SaidaMaterial(db.Model):
    __tablename__ = 'saida_materiais'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey('solicitacoes.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    
    quantidade_solicitada = db.Column(db.Integer, nullable=False, default=1) 
    
    quantidade_saida = db.Column(db.Integer, nullable=False)
    data_saida = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    retornado = db.Column(db.Boolean, default=False, nullable=False)
    
    solicitacao = db.relationship('Solicitacao', backref=db.backref('materiais_usados', lazy=True, cascade="all, delete-orphan"))
    produto = db.relationship('Produto')

    def __repr__(self):
        return f'<SaidaMaterial {self.quantidade_saida}x {self.produto.nome} para Chamado {self.solicitacao_id}>'

    

class Comentario(db.Model):
    __tablename__ = 'comentarios'
    
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    solicitacao_id = db.Column(db.Integer, db.ForeignKey('solicitacoes.id'), nullable=False)
    
    usuario = db.relationship('Usuario')
    solicitacao = db.relationship('Solicitacao', backref=db.backref('comentarios', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<Comentario {self.id} para Chamado {self.solicitacao_id}>'