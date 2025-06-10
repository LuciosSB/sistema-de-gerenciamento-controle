from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file, session
import pdfkit
from io import BytesIO
from db_setup import db
from models import Produto, Setor, Solicitacao, Usuario, SaidaMaterial
from sqlalchemy.orm import Session
import json
from datetime import datetime
import base64
import os
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import Config
from datetime import datetime, timedelta

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

pdfkit_config = pdfkit.configuration(wkhtmltopdf=app.config['WKHTMLTOPDF_PATH'])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Faça login para acessar esta página.', 'warning')
                return redirect(url_for('login'))
            
            if not current_user.has_permission(permission):
                flash('Você não tem permissão para acessar esta página.', 'error')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def convert_logo_to_base64(image_path):
    try:
        if not os.path.exists(image_path):
            return None
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception:
        return None

# --- ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.check_password(password) and usuario.ativo:
            login_user(usuario)
            flash(f'Bem-vindo, {usuario.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Username ou senha incorretos, ou usuário inativo.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- ROTAS DE PRODUTOS ---
@app.route('/cadastro', methods=['GET', 'POST'])
@login_required
@permission_required('cadastrar_produto')
def cadastro_produto():
    if request.method == 'POST':
        codigo_barras = request.form['codigo_barras']
        nome = request.form['nome']
        quantidade = request.form['quantidade']
        tipo_item = request.form['tipo_item']
        
        produto_existente = Produto.query.filter_by(codigo_barras=codigo_barras).first()
        if produto_existente:
            flash('Código de barras já cadastrado!', 'error')
            return render_template('cadastro.html')
        
        try:
            produto = Produto(codigo_barras=codigo_barras, nome=nome, quantidade=int(quantidade), tipo_item=tipo_item)
            db.session.add(produto)
            db.session.commit()
            flash('Item/Produto cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar: {e}', 'error')
    
    return render_template('cadastro.html')

@app.route('/produtos')
@login_required
@permission_required('listar_produtos')
def listar_produtos():
    produtos = Produto.query.all()
    return render_template('produtos.html', produtos=produtos)

@app.route('/atualizar', methods=['GET', 'POST'])
@login_required
@permission_required('atualizar_produto')
def selecionar_produto_atualizar():
    if request.method == 'POST':
        produto_id = request.form['produto_id']
        return redirect(url_for('atualizar_produto', produto_id=produto_id))
    produtos = Produto.query.all()
    return render_template('selecionar_produto.html', produtos=produtos)

@app.route('/atualizar/<int:produto_id>', methods=['GET', 'POST'])
@login_required
@permission_required('atualizar_produto')
def atualizar_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    if request.method == 'POST':
        try:
            produto.codigo_barras = request.form['codigo_barras']
            produto.nome = request.form['nome']
            produto.quantidade = int(request.form['quantidade'])
            produto.tipo_item = request.form['tipo_item']
            db.session.commit()
            flash('Item/Produto atualizado com sucesso!', 'success')
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {e}', 'error')
    return render_template('atualizar.html', produto=produto)

# --- ROTAS DE SOLICITAÇÃO ---
@app.route('/portal_solicitacoes', methods=['GET', 'POST'])
def portal_solicitacoes():
    if request.method == 'POST':
        try:
            novo_chamado = Solicitacao(
                nome_solicitante=request.form.get('nome_solicitante', '').strip(),
                setor=request.form.get('setor', '').strip(),
                titulo=request.form.get('titulo', '').strip(),
                categoria=request.form.get('categoria', 'Geral').strip(),
                urgencia=request.form.get('urgencia', 'baixa').strip(),
                descricao=request.form.get('descricao', '').strip(),
                status='pendente',
                data_solicitacao=datetime.now()
            )
            if not novo_chamado.nome_solicitante or not novo_chamado.setor or not novo_chamado.titulo:
                flash('Os campos Nome, Setor e Título são obrigatórios.', 'error')
                return render_template('portal_solicitacoes.html')
            db.session.add(novo_chamado)
            db.session.commit()
            flash('Chamado de manutenção aberto com sucesso!', 'success')
            return redirect(url_for('portal_solicitacoes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao abrir chamado: {e}', 'error')
    return render_template('portal_solicitacoes.html')

@app.route('/gerenciar_solicitacoes')
@login_required
@permission_required('gerenciar_solicitacoes')
def gerenciar_solicitacoes():
    todas_as_solicitacoes = Solicitacao.query.order_by(Solicitacao.data_solicitacao.desc()).all()
    limite_de_tempo = datetime.utcnow() - timedelta(days=1)
    solicitacoes_visiveis = [s for s in todas_as_solicitacoes if not (s.status == 'entregue' and s.data_atualizacao and s.data_atualizacao < limite_de_tempo)]
    return render_template('gerenciar_solicitacoes.html', solicitacoes=solicitacoes_visiveis)

@app.route('/gerenciar_solicitacoes/<int:solicitacao_id>')
@login_required
@permission_required('gerenciar_solicitacoes')
def gerenciar_solicitacoes_detalhes(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    produtos_disponiveis = Produto.query.order_by(Produto.nome).all()
    return render_template('gerenciar_solicitacoes_detalhes.html', solicitacao=solicitacao, produtos_disponiveis=produtos_disponiveis)

@app.route('/atualizar_status_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def atualizar_status_solicitacao(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    novo_status = request.form.get('status')
    if novo_status not in ['pendente', 'aprovada', 'rejeitada', 'entregue']:
        flash('Status inválido.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
    solicitacao.status = novo_status
    solicitacao.data_atualizacao = datetime.now()
    if novo_status == 'rejeitada':
        motivo_rejeicao = request.form.get('motivo_rejeicao', '').strip()
        if not motivo_rejeicao:
            flash('O motivo é obrigatório para rejeitar um chamado.', 'error')
            db.session.rollback()
            return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
        solicitacao.motivo_rejeicao = motivo_rejeicao
    else:
        solicitacao.motivo_rejeicao = None
    try:
        db.session.commit()
        flash(f'Status do chamado #{solicitacao_id} atualizado para "{novo_status.capitalize()}"!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar status: {e}', 'error')
    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

@app.route('/excluir_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def excluir_solicitacao(solicitacao_id):
    try:
        solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
        db.session.delete(solicitacao)
        db.session.commit()
        flash(f'Chamado #{solicitacao_id} excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir chamado: {e}', 'error')
    return redirect(url_for('gerenciar_solicitacoes'))

@app.route('/solicitacao/<int:solicitacao_id>/adicionar_item', methods=['POST'])
@login_required
@permission_required('saida_produto')
def adicionar_item_solicitacao(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    if solicitacao.status != 'aprovada':
        flash('Só é possível adicionar itens a chamados com status "Aprovado".', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
    try:
        produto_id = request.form.get('produto_id')
        quantidade_saida = int(request.form.get('quantidade_saida'))
        produto = Produto.query.get(produto_id)
        if not produto or quantidade_saida <= 0:
            flash('Dados inválidos.', 'error')
        elif produto.quantidade < quantidade_saida:
            flash(f'Estoque insuficiente para "{produto.nome}". Restam: {produto.quantidade}.', 'error')
        else:
            produto.quantidade -= quantidade_saida
            nova_saida = SaidaMaterial(solicitacao_id=solicitacao_id, produto_id=produto_id, quantidade_saida=quantidade_saida)
            db.session.add(nova_saida)
            db.session.commit()
            flash(f'Item "{produto.nome}" adicionado ao chamado!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao adicionar item: {e}', 'error')
    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

# ===================================================================
# NOVA ROTA PARA GERAR O PDF DA REQUISIÇÃO
# ===================================================================
@app.route('/solicitacao/<int:solicitacao_id>/gerar_pdf')
@login_required
@permission_required('saida_produto')
def gerar_requisicao_pdf(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    saidas_de_material = solicitacao.materiais_usados
    
    if not saidas_de_material:
        flash('Nenhum material foi retirado para este chamado. Não é possível gerar PDF.', 'warning')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
    
    produtos_para_pdf = [{'codigo_barras': s.produto.codigo_barras, 'nome': s.produto.nome, 'quantidade_solicitada': s.quantidade_saida} for s in saidas_de_material]
    
    data_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    logo_base64 = convert_logo_to_base64('static/logodmtt.png')
    
    rendered = render_template('saida_pdf.html', produtos=produtos_para_pdf, setor=solicitacao.setor, data_pedido=data_hora, logo_base64=logo_base64)
    pdf = pdfkit.from_string(rendered, False, configuration=pdfkit_config, options={'enable-local-file-access': None})
    
    return send_file(BytesIO(pdf), download_name=f'Requisicao_Chamado_{solicitacao.id}.pdf', as_attachment=True)

# --- ROTAS DE USUÁRIOS E COMPATIBILIDADE ---
@app.route('/quantidade_produto/<int:produto_id>', methods=['GET'])
@login_required
def quantidade_produto(produto_id):
    produto = Produto.query.get(produto_id)
    return jsonify({'quantidade': produto.quantidade}) if produto else jsonify({'quantidade': 0})

@app.route('/cadastro_usuario', methods=['GET', 'POST'])
@login_required
def cadastro_usuario():
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    # ... Lógica de cadastro
    return render_template('cadastro_usuario.html')

@app.route('/lista_usuarios')
@login_required
def lista_usuarios():
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    usuarios = Usuario.query.all()
    return render_template('lista_usuarios.html', usuarios=usuarios)

@app.route('/atualizar_cadastro/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
def atualizar_cadastro(usuario_id):
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    usuario = Usuario.query.get_or_404(usuario_id)
    # ... Lógica de atualização
    return render_template('atualizar_cadastro.html', usuario=usuario)

@app.route('/excluir_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def excluir_usuario(usuario_id):
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    # ... Lógica de exclusão
    return redirect(url_for('lista_usuarios'))

@app.route('/exibir_index')
def exibir_index():
    return redirect(url_for('login'))

@app.route('/exibir_login')
def exibir_login():
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        if not Usuario.query.filter_by(username='admin').first():
            admin = Usuario(username='admin', dados='Admin TI', tipo_usuario='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Usuário 'admin' criado com a senha 'admin123'.")
    
    app.run(host='0.0.0.0', port=5000, debug=True)