from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file, session, send_from_directory
import pdfkit
from io import BytesIO
from db_setup import db
from models import Produto, Setor, Solicitacao, Usuario, SaidaMaterial, Comentario, HistoricoAcoes, Anexo
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from urllib.parse import urlparse
import json
from datetime import datetime
import base64
import os
import sys
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import Config
import pytz
from datetime import datetime, timedelta
from flask_migrate import Migrate
import re
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, ProgrammingError
from flask_migrate import upgrade
from flask_apscheduler import APScheduler
from werkzeug.utils import secure_filename
import uuid 

if getattr(sys, 'frozen', False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.abspath(os.path.dirname(__file__))


app = Flask(__name__)

app.config.from_object(Config)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)
migrate = Migrate(app, db)

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    path_wkhtmltopdf = os.path.join(sys._MEIPASS, 'binarios_pdf', 'wkhtmltopdf.exe')
else:
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
pdfkit_config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'
login_manager.login_message_category = 'info'

@app.before_request
def before_request():
    """Define o tempo de vida da sessão e a renova a cada requisição."""
    # Define o tempo de vida da sessão para 24 horas
    app.permanent_session_lifetime = timedelta(hours=24)
    # Marca a sessão como permanente para que o tempo de vida seja aplicado
    session.permanent = True
    # A cada requisição, a sessão é "renovada", reiniciando o timer de inatividade.
    # Esta linha é opcional, mas recomendada para não deslogar usuários ativos.
    session.modified = True


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            print(f"DEBUG: Verificando permissão '{permission}' para o usuário '{current_user.username}' que é do tipo '{current_user.tipo_usuario}'")
            
            if not current_user.has_permission(permission): #
                flash('Você não tem permissão para acessar esta página.', 'error') #
                return redirect(url_for('dashboard')) #
            return f(*args, **kwargs) #
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
    
def to_localtime(utc_datetime):
    if not utc_datetime:
        return ""
    local_tz = pytz.timezone('America/Maceio') # Fuso horário de Alagoas
    local_dt = utc_datetime.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return local_dt.strftime('%d/%m/%Y às %H:%M')

app.jinja_env.filters['localtime'] = to_localtime

# --- ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO ---
@app.route('/')
@login_required
def index():
    solicitacoes_pendentes = 0
    produtos_baixo_estoque = 0
    total_produtos = 0

    if current_user.tipo_usuario == 'admin':
        solicitacoes_pendentes = Solicitacao.query.filter_by(status='pendente').count()
        produtos_baixo_estoque = Produto.query.filter(Produto.quantidade < 5).count()
        total_produtos = Produto.query.count()

    return render_template('index.html',
                         solicitacoes_pendentes=solicitacoes_pendentes,
                         produtos_baixo_estoque=produtos_baixo_estoque,
                         total_produtos=total_produtos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.check_password(password) and usuario.ativo:
            login_user(usuario)
            flash(f'Bem-vindo, {usuario.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Username ou senha incorretos, ou usuário inativo.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('index'))

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
        
        produto_existente = None
        if codigo_barras:
            produto_existente = Produto.query.filter_by(codigo_barras=codigo_barras).first()

        if produto_existente:
            flash('Código de barras já cadastrado!', 'error')
            return render_template('cadastro.html')
        
        try:
            produto = Produto(
                codigo_barras=codigo_barras, 
                nome=nome, 
                quantidade=int(quantidade), 
                quantidade_inicial=int(quantidade),
                tipo_item=tipo_item
            )
            db.session.add(produto) 

            historico_cadastro = HistoricoAcoes(
                usuario_id=current_user.id,
                tipo_acao='produto_criado',
                detalhes=f"Produto '{produto.nome}' cadastrado com quantidade inicial de {produto.quantidade}.",
                produto_id=produto.id
            )
            db.session.add(historico_cadastro)

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
    produtos = Produto.query.order_by(Produto.nome).all()
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
            old_nome = produto.nome
            old_quantidade = produto.quantidade
            produto.codigo_barras = request.form['codigo_barras'] 
            produto.nome = request.form['nome'] 
            produto.quantidade = int(request.form['quantidade']) 
            produto.tipo_item = request.form['tipo_item'] 

            detalhes = f"Produto '{old_nome}' (ID: {produto.id}) atualizado. "
            if old_quantidade != produto.quantidade:
                detalhes += f"Quantidade alterada de {old_quantidade} para {produto.quantidade}. "
            if old_nome != produto.nome:
                detalhes += f"Nome alterado para '{produto.nome}'. "

            historico_atualizacao = HistoricoAcoes(
                usuario_id=current_user.id,
                tipo_acao='produto_atualizado',
                detalhes=detalhes.strip(), # .strip() remove espaços extras no final
                produto_id=produto.id
            )
            db.session.add(historico_atualizacao)

            db.session.commit() #
            flash('Item/Produto atualizado com sucesso!', 'success')
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback() #
            flash(f'Erro ao atualizar: {e}', 'error')
            
    return render_template('atualizar.html', produto=produto)


# --- COLE ISSO NO SEU APP.PY ---

@app.route('/saida_produto', methods=['POST'])
@login_required
def saida_produto():
    solicitacao_id = request.form.get('solicitacao_id')
    produto_id = request.form.get('produto_id')
    quantidade = int(request.form.get('quantidade'))

    produto = Produto.query.get(produto_id)

    if not produto:
        flash('Produto não encontrado.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    if produto.quantidade < quantidade:
        flash(f'Estoque insuficiente! Restam apenas {produto.quantidade} unidades.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    try:
        produto.quantidade -= quantidade

        nova_saida = SaidaMaterial(
            solicitacao_id=solicitacao_id,
            produto_id=produto_id,
            usuario_id=current_user.id,
            quantidade_saida=quantidade,
            data_saida=datetime.utcnow()
        )
        db.session.add(nova_saida)

        hist = HistoricoAcoes(
            data_acao=datetime.utcnow(),
            tipo_acao="Saída de Material",
            detalhes=f"Registrou saída de {quantidade}x {produto.nome}",
            solicitacao_id=solicitacao_id,
            usuario_id=current_user.id,
            produto_id=produto_id
        )
        db.session.add(hist)

        db.session.commit()
        flash(f'Saída de {quantidade}x {produto.nome} registrada com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar saída: {str(e)}', 'error')

    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

@app.route('/excluir_produto/<int:produto_id>', methods=['POST'])
@login_required
def excluir_produto(produto_id):
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado. Apenas administradores podem excluir itens.', 'error')
        return redirect(url_for('listar_produtos'))
    produto = Produto.query.get_or_404(produto_id)

    try:
        db.session.delete(produto)
        db.session.commit()
        flash(f'Produto "{produto.nome}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Não é possível excluir este produto pois ele já faz parte de históricos de solicitações antigas.',
              'error')

    return redirect(url_for('listar_produtos'))


@app.route('/portal_solicitacoes', methods=['GET', 'POST'])
def portal_solicitacoes():
    if request.method == 'POST':
        try:
            nome = request.form.get('nome_solicitante', '').strip()
            setor = request.form.get('setor', '').strip()
            titulo = request.form.get('titulo', '').strip()
            categoria = request.form.get('categoria', 'Geral').strip()
            descricao = request.form.get('descricao', '').strip()
            urgencia = request.form.get('urgencia', 'baixa')  # Novo campo!

            if not all([nome, setor, titulo, categoria]):
                flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
                return render_template('portal_solicitacoes.html')

            novo_chamado = Solicitacao(
                nome_solicitante=nome,
                setor=setor,
                titulo=titulo,
                categoria=categoria,
                descricao=descricao,
                urgencia=urgencia,
                status='pendente'
            )
            db.session.add(novo_chamado)
            db.session.flush()
            arquivos = request.files.getlist('anexos')
            for file in arquivos:
                if file and file.filename != '' and allowed_file(file.filename):
                    original_filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
                    caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(caminho_salvar)
                    novo_anexo = Anexo(
                        nome_arquivo=unique_filename,
                        tipo_anexo='abertura',  # Tipo para identificar que veio da abertura
                        solicitacao_id=novo_chamado.id
                    )
                    db.session.add(novo_anexo)

            autor_id = current_user.id if current_user.is_authenticated else 1
            detalhes_acao = (f"Chamado criado por '{nome}' via Portal."
                             if not current_user.is_authenticated
                             else f"Chamado criado pelo usuário interno '{current_user.username}'.")

            historico_criacao = HistoricoAcoes(
                solicitacao_id=novo_chamado.id,
                usuario_id=autor_id,
                tipo_acao='chamado_criado',
                detalhes=detalhes_acao
            )
            db.session.add(historico_criacao)

            db.session.commit()
            flash(f'Chamado #{novo_chamado.id} aberto com sucesso! Acompanhe na lista.', 'success')

            if current_user.is_authenticated:
                return redirect(url_for('lista_solicitacoes'))
            else:
                return redirect(url_for('portal_solicitacoes'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao abrir chamado: {str(e)}', 'error')
            print(f"ERRO: {str(e)}")

    return render_template('portal_solicitacoes.html')

@app.route('/portal_arcondicionado', methods=['GET', 'POST'])
def portal_arcondicionado():
    if request.method == 'POST':
        try:
            # Pega os dados do formulário
            patrimonio = request.form.get('patrimonio_ativo', '').strip()
            nome_solicitante = request.form.get('nome_solicitante', '').strip()
            setor = request.form.get('setor', '').strip()
            titulo = request.form.get('titulo', '').strip()
            descricao = request.form.get('descricao', '').strip()
            if not all([patrimonio, nome_solicitante, setor, titulo]):
                flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
                return redirect(url_for('portal_arcondicionado'))

            novo_chamado = Solicitacao(
                nome_solicitante=nome_solicitante,
                setor=setor,
                titulo=titulo,
                categoria='Ar-Condicionado',  # Categoria é fixa
                patrimonio_ativo=patrimonio,
                descricao=descricao,
                status='pendente'
            )
            db.session.add(novo_chamado)
            db.session.flush()

            autor_id = current_user.id if current_user.is_authenticated else 1
            detalhes_acao = f"Chamado de Ar-Condicionado criado para o patrimônio '{patrimonio}' pelo solicitante '{nome_solicitante}'."
            
            historico_criacao = HistoricoAcoes(
                solicitacao_id=novo_chamado.id,
                usuario_id=autor_id,
                tipo_acao='chamado_criado',
                detalhes=detalhes_acao
            )
            db.session.add(historico_criacao)
            
            db.session.commit()
            flash(f'Chamado de Ar-Condicionado aberto com sucesso! O ID do chamado é #{novo_chamado.id}, confira no Portal', 'success')
            return redirect(url_for('portal_arcondicionado'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao abrir chamado: {e}', 'error')
            
    return render_template('portal_arcondicionado.html')

@app.route('/gerenciar_solicitacoes')
@login_required
@permission_required('gerenciar_solicitacoes')
def gerenciar_solicitacoes():
    now = datetime.utcnow()
    limite_de_tempo = now - timedelta(minutes=1)
    solicitacoes_visiveis = Solicitacao.query.filter(
        db.or_(
            Solicitacao.status.in_(['pendente','em_analise','aprovada']),
            db.and_(
                Solicitacao.status.in_(['entregue', 'rejeitada', 'excluido']),
                Solicitacao.data_atualizacao.isnot(None),
                Solicitacao.data_atualizacao > limite_de_tempo
            )
        )
    ).order_by(Solicitacao.data_solicitacao.desc()).all()
    
    return render_template('gerenciar_solicitacoes.html', solicitacoes=solicitacoes_visiveis)

@app.route('/gerenciar_solicitacoes/<int:solicitacao_id>', methods=['GET', 'POST'])
@login_required
def gerenciar_solicitacoes_detalhes(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    if request.method == 'POST':
        novo_status = request.form.get('novo_status')
        observacoes = request.form.get('observacoes')

        if not observacoes:
            flash('É obrigatório informar uma observação para mudar o status.', 'error')
        else:
            try:
                status_antigo = solicitacao.status
                solicitacao.status = novo_status
                hist = HistoricoAcoes(
                    data_acao=datetime.utcnow(),
                    tipo_acao=f"Alteração de Status",
                    detalhes=f"De '{status_antigo.upper()}' para '{novo_status.upper()}'. Motivo: {observacoes}",
                    solicitacao_id=solicitacao.id,
                    usuario_id=current_user.id
                )
                db.session.add(hist)

                db.session.commit()
                flash('Status da solicitação atualizado com sucesso!', 'success')

            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao atualizar status: {str(e)}', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

    produtos_disponiveis = Produto.query.filter(Produto.quantidade > 0).order_by(Produto.nome).all()

    return render_template('gerenciar_solicitacoes_detalhes.html',
                           solicitacao=solicitacao,
                           produtos_disponiveis=produtos_disponiveis)

@app.route('/atualizar_status_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def atualizar_status_solicitacao(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    status_antigo = solicitacao.status
    novo_status = request.form.get('status')

    if novo_status == 'aprovada' and current_user.tipo_usuario not in ['manutencao', 'admin']:
        flash('Você não tem permissão para aprovar um chamado.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    if novo_status not in ['pendente', 'em_analise', 'aprovada', 'rejeitada', 'entregue']:
        flash('Status inválido.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
    
    solicitacao.status = novo_status
    solicitacao.data_atualizacao = datetime.now()
    
    detalhes_historico = f'Status alterado de "{status_antigo.capitalize()}" para "{novo_status.capitalize()}".'

    if novo_status == 'rejeitada':
        motivo_rejeicao = request.form.get('motivo_rejeicao', '').strip()
        if not motivo_rejeicao:
            flash('O motivo é obrigatório para rejeitar um chamado.', 'error')
            db.session.rollback()
            return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
        solicitacao.motivo_rejeicao = motivo_rejeicao
        detalhes_historico += f" Motivo: {motivo_rejeicao}"
    else:
        solicitacao.motivo_rejeicao = None
        
    try:
        historico_status = HistoricoAcoes(
            solicitacao_id=solicitacao_id,
            usuario_id=current_user.id,
            tipo_acao='status_alterado',
            detalhes=detalhes_historico
        )
        db.session.add(historico_status)
        
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
        
        solicitacao.status = 'excluido'
        solicitacao.data_atualizacao = datetime.utcnow()
        
        historico_exclusao = HistoricoAcoes(
            solicitacao_id=solicitacao_id,
            usuario_id=current_user.id,
            tipo_acao='chamado_excluido',
            detalhes='O chamado foi movido para a lixeira.'
        )
        db.session.add(historico_exclusao)
        
        db.session.commit()
        flash(f'Chamado #{solicitacao.id} foi movido para a lixeira.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir chamado: {e}', 'error')
    return redirect(url_for('gerenciar_solicitacoes'))

@app.route('/solicitacao/<int:solicitacao_id>/definir_urgencia', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes') 
def definir_urgencia(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    nova_urgencia = request.form.get('nova_urgencia')

    if not nova_urgencia in ['baixa', 'media', 'alta', 'critica']:
        flash('Nível de urgência inválido.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

    urgencia_antiga = solicitacao.urgencia
    solicitacao.urgencia = nova_urgencia
    
    historico_urgencia = HistoricoAcoes(
        solicitacao_id=solicitacao.id,
        usuario_id=current_user.id,
        tipo_acao='urgencia_alterada',
        detalhes=f"Nível de urgência alterado de '{urgencia_antiga.capitalize()}' para '{nova_urgencia.capitalize()}'."
    )
    db.session.add(historico_urgencia)
    
    try:
        db.session.commit()
        flash('Nível de urgência atualizado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar urgência: {e}', 'error')
        
    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

@app.route('/solicitacao/<int:solicitacao_id>/adicionar_item', methods=['POST'])
@login_required
@permission_required('saida_produto')
def adicionar_item_solicitacao(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    
    if solicitacao.status != 'aprovada':
        flash('Só é possível adicionar itens a chamados com status "Aprovado".', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    produtos_ids = request.form.getlist('produto_id[]')
    quantidades_solicitada_str = request.form.getlist('quantidade_solicitada[]')
    quantidades_saida_str = request.form.getlist('quantidade_saida[]')

    itens_para_adicionar = []
    erros = []

    for i in range(len(produtos_ids)):
        produto_id = produtos_ids[i]
        qtd_solicitada_str = quantidades_solicitada_str[i]
        qtd_saida_str = quantidades_saida_str[i]

        if not produto_id or not qtd_saida_str or not qtd_solicitada_str:
            continue
        try:
            quantidade_solicitada = int(qtd_solicitada_str)
            quantidade_saida = int(qtd_saida_str)
            produto = Produto.query.get(produto_id)

            if not produto:
                erros.append(f"Produto com ID {produto_id} não encontrado.")
            elif quantidade_saida <= 0 or quantidade_solicitada <= 0:
                erros.append("As quantidades devem ser maiores que zero.")
            elif produto.quantidade < quantidade_saida:
                erros.append(f'Estoque insuficiente para "{produto.nome}". Pedido: {quantidade_saida}, Disponível: {produto.quantidade}.')
            else:
                itens_para_adicionar.append({
                    'produto': produto, 
                    'quantidade_saida': quantidade_saida,
                    'quantidade_solicitada': quantidade_solicitada
                })
        except ValueError:
            erros.append("Quantidade inválida fornecida.")

    if erros:
        for erro in erros:
            flash(erro, 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
    
    if not itens_para_adicionar:
        flash("Nenhum item válido foi adicionado.", "warning")
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    try:
        for item in itens_para_adicionar:
            produto = item['produto']
            produto.quantidade -= item['quantidade_saida']
            
            nova_saida = SaidaMaterial(
                solicitacao_id=solicitacao_id,
                produto_id=produto.id,
                quantidade_solicitada=item['quantidade_solicitada'],
                quantidade_saida=item['quantidade_saida'],
                usuario_id=current_user.id 
            )
            db.session.add(nova_saida)
            
            detalhes_adicao = f"{item['quantidade_saida']}x {produto.nome} adicionado(s) ao chamado #{solicitacao_id}."
            historico_adicao = HistoricoAcoes(
                solicitacao_id=solicitacao_id,
                usuario_id=current_user.id,
                tipo_acao='item_adicionado',
                detalhes=detalhes_adicao,
                produto_id=produto.id
            )
            db.session.add(historico_adicao)
            
        db.session.commit()
        flash(f'{len(itens_para_adicionar)} tipo(s) de item(ns) adicionado(s) ao chamado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao salvar os itens: {e}', 'error')

    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

@app.route('/solicitacao/<int:solicitacao_id>/remover_item/<int:saida_id>', methods=['POST'])
@login_required
@permission_required('saida_produto')
def remover_item_solicitacao(solicitacao_id, saida_id):
    saida_material = SaidaMaterial.query.get_or_404(saida_id)

    if saida_material.solicitacao_id != solicitacao_id:
        flash('Operação inválida. O item não pertence a este chamado.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    if saida_material.retornado:
        flash('Não é possível remover um item que já foi oficialmente devolvido.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    produto = saida_material.produto
    quantidade_removida = saida_material.quantidade_saida
    nome_produto = produto.nome

    try:
        produto.quantidade += quantidade_removida

        novo_historico = HistoricoAcoes(
            solicitacao_id=solicitacao_id,
            usuario_id=current_user.id,
            tipo_acao='item_removido',
            detalhes=f'Item removido do chamado: {quantidade_removida}x {nome_produto}.',
            produto_id=produto.id
        )
        db.session.add(novo_historico)

        db.session.delete(saida_material)
        
        db.session.commit()
        flash(f'Item "{nome_produto}" removido e retornado ao estoque com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover o item: {e}', 'error')

    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

@app.route('/solicitacao/<int:solicitacao_id>/gerar_pdf')
@login_required
@permission_required('saida_produto')
def gerar_requisicao_pdf(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    saidas_de_material = solicitacao.materiais_usados
    if not saidas_de_material:
        flash('Nenhum material foi retirado para este chamado. Não é possível gerar PDF.', 'warning')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
    
    produtos_para_pdf = [
        {
            'codigo_barras': saida.produto.codigo_barras,
            'nome': saida.produto.nome,
            'quantidade_solicitada': saida.quantidade_solicitada,
            'quantidade_fornecida': saida.quantidade_saida
        }
        for saida in saidas_de_material
    ]
    data_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    # Usa o 'basedir' universal para construir o caminho até a logo
    logo_path = os.path.join(basedir, 'static', 'dmttlogo.png')
    logo_base64 = convert_logo_to_base64(logo_path)

    rendered = render_template('saida_pdf.html', 
                               solicitacao=solicitacao,
                               produtos=produtos_para_pdf,
                               data_pedido=data_hora, 
                               logo_base64=logo_base64)
                               
    # Mantemos a opção 'enable-local-file-access' como True para garantir
    pdf = pdfkit.from_string(rendered, False, configuration=pdfkit_config, options={'enable-local-file-access': True})
    return send_file(BytesIO(pdf), download_name=f'Requisicao_Chamado_{solicitacao.id}.pdf', as_attachment=True)

@app.route('/solicitacao/<int:solicitacao_id>/confirmar_devolucao', methods=['POST'])
@login_required
@permission_required('saida_produto')
def confirmar_devolucao_itens(solicitacao_id):
    try:
        saidas_pendentes = SaidaMaterial.query.filter_by(solicitacao_id=solicitacao_id, retornado=False).all()
        itens_devolvidos_count = 0

        for saida in saidas_pendentes:
            qtd_retornada_str = request.form.get(f'quantidade_retornada_{saida.id}')
            
            if qtd_retornada_str is None:
                continue

            qtd_retornada = int(qtd_retornada_str)
            produto = saida.produto

            if qtd_retornada > 0:
                produto.quantidade += qtd_retornada
                db.session.add(produto)
                
                detalhes_devolucao = f"{qtd_retornada}x {produto.nome} devolvido(s) ao estoque do chamado #{solicitacao_id}."
                historico_devolucao = HistoricoAcoes(
                    solicitacao_id=solicitacao_id,
                    usuario_id=current_user.id,
                    tipo_acao='item_devolvido',
                    detalhes=detalhes_devolucao,
                    produto_id=produto.id
                )
                db.session.add(historico_devolucao)
                itens_devolvidos_count += 1

            qtd_saida = saida.quantidade_saida
            qtd_consumida = qtd_saida - qtd_retornada
            if qtd_consumida > 0:
                detalhes_consumo = f"{qtd_consumida}x {produto.nome} foi/foram consumido(s) no chamado #{solicitacao_id}."
                historico_consumo = HistoricoAcoes(
                    solicitacao_id=solicitacao_id,
                    usuario_id=current_user.id,
                    tipo_acao='item_consumido',
                    detalhes=detalhes_consumo,
                    produto_id=produto.id
                )
                db.session.add(historico_consumo)

            saida.retornado = True
            db.session.add(saida)

        if itens_devolvidos_count > 0:
            flash(f'{itens_devolvidos_count} tipo(s) de item(ns) tiveram sua devolução processada!', 'success')
        else:
            flash('Nenhuma nova devolução foi registrada. O chamado foi fechado.', 'info')

        db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao processar a devolução: {e}', 'error')
        
    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

@app.route('/solicitacao/<int:solicitacao_id>/adicionar_comentario', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes') 
def adicionar_comentario(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    texto_comentario = request.form.get('texto_comentario', '').strip()
    if not texto_comentario:
        flash('O campo de comentário não pode estar vazio.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    try:
        novo_comentario = Comentario(
            texto=texto_comentario,
            usuario_id=current_user.id, 
            solicitacao_id=solicitacao.id
        )
        db.session.add(novo_comentario)

        historico_comentario = HistoricoAcoes(
            solicitacao_id=solicitacao_id,
            usuario_id=current_user.id,
            tipo_acao='comentario_adicionado',
            detalhes=f'Adicionou um comentário: "{texto_comentario}"'
        )
        db.session.add(historico_comentario)

        db.session.commit()
        flash('Comentário adicionado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao adicionar comentário: {e}', 'error')

    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

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
    
    if request.method == 'POST': 
        username = request.form.get('username') 
        password = request.form.get('password') 
        dados = request.form.get('dados') 
        tipo_usuario = request.form.get('tipo_usuario') 

        if not all([username, password, dados, tipo_usuario]): 
            flash('Todos os campos são obrigatórios.', 'error') 
            return redirect(url_for('cadastro_usuario')) 
        
        if Usuario.query.filter_by(username=username).first(): 
            flash('Este nome de usuário já existe.', 'error') 
            return redirect(url_for('cadastro_usuario')) 

        try:
            # Cria o objeto do novo usuário e adiciona à sessão
            novo_usuario = Usuario( 
                username=username, 
                dados=dados, 
                tipo_usuario=tipo_usuario 
            )
            novo_usuario.set_password(password) 
            db.session.add(novo_usuario) 
            historico_user = HistoricoAcoes(
                usuario_id=current_user.id,
                tipo_acao='usuario_criado',
                detalhes=f"Usuário '{novo_usuario.username}' (Tipo: {novo_usuario.tipo_usuario}) foi criado."
            )
            db.session.add(historico_user)
            db.session.commit()

            flash(f'Usuário "{username}" cadastrado com sucesso!', 'success') 
            return redirect(url_for('lista_usuarios')) 
        except Exception as e:
            db.session.rollback() 
            flash(f'Ocorreu um erro ao cadastrar o usuário: {e}', 'error') 
            return redirect(url_for('cadastro_usuario')) 

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
    
    if request.method == 'POST': 
        username = request.form.get('username') 
        dados = request.form.get('dados') 
        tipo_usuario = request.form.get('tipo_usuario') 
        nova_senha = request.form.get('nova_senha') 
        ativo = 'ativo' in request.form 

        usuario_existente = Usuario.query.filter(Usuario.username == username, Usuario.id != usuario_id).first() 
        if usuario_existente: 
            flash(f'O nome de usuário "{username}" já está em uso.', 'error') 
            return redirect(url_for('atualizar_cadastro', usuario_id=usuario_id)) 

        try:
            usuario.username = username 
            usuario.dados = dados 
            usuario.tipo_usuario = tipo_usuario 
            usuario.ativo = ativo 

            if nova_senha: 
                usuario.set_password(nova_senha) 
            
            # Cria o registro de histórico para esta ação
            historico_att_user = HistoricoAcoes(
                usuario_id=current_user.id,
                tipo_acao='usuario_atualizado',
                detalhes=f"Dados do usuário '{usuario.username}' (ID: {usuario.id}) foram atualizados."
            )
            db.session.add(historico_att_user)
            db.session.commit()

            flash('Cadastro do usuário atualizado com sucesso!', 'success') 
            return redirect(url_for('lista_usuarios')) 
        except Exception as e:
            db.session.rollback() 
            flash(f'Erro ao atualizar o cadastro: {e}', 'error') 
            return redirect(url_for('atualizar_cadastro', usuario_id=usuario_id)) 

    return render_template('atualizar_cadastro.html', usuario=usuario) 

@app.route('/excluir_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def excluir_usuario(usuario_id):
    if current_user.tipo_usuario != 'admin': 
        flash('Acesso negado.', 'error') 
        return redirect(url_for('lista_usuarios')) 
        
    if current_user.id == usuario_id: 
        flash('Você não pode excluir seu próprio usuário.', 'error') 
        return redirect(url_for('lista_usuarios')) 
        
    try:
        usuario_para_excluir = Usuario.query.get_or_404(usuario_id) 
        nome_usuario_excluido = usuario_para_excluir.username
        # Cria o registro de histórico para a exclusão
        historico_del_user = HistoricoAcoes(
            usuario_id=current_user.id,
            tipo_acao='usuario_excluido',
            detalhes=f"Usuário '{nome_usuario_excluido}' foi permanentemente excluído."
        )
        db.session.add(historico_del_user)
        # Prepara a exclusão do usuário e o registro do histórico para serem commitados juntos
        db.session.delete(usuario_para_excluir) 
        db.session.commit() 
        
        flash(f'Usuário "{nome_usuario_excluido}" foi excluído permanentemente.', 'success')
    except Exception as e:
        db.session.rollback() 
        flash(f'Erro ao excluir usuário: {e}', 'error') 
        
    return redirect(url_for('lista_usuarios'))


@app.route('/lista_solicitacoes')
def lista_solicitacoes():
    solicitacoes = Solicitacao.query.order_by(Solicitacao.data_solicitacao.desc()).limit(100).all()

    return render_template('lista_solicitacoes.html', solicitacoes=solicitacoes)


@app.route('/processar_retorno_material/<int:saida_id>/<acao>', methods=['POST'])
@login_required
def processar_retorno_material(saida_id, acao):
    if current_user.tipo_usuario == 'usuario_gerenciador':
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))

    saida = SaidaMaterial.query.get_or_404(saida_id)
    produto = Produto.query.get(saida.produto_id)
    solicitacao = Solicitacao.query.get(saida.solicitacao_id)

    if saida.status_retorno != 'pendente':
        flash('Este item já foi processado anteriormente.', 'warning')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

    try:
        if acao == 'devolver':
            produto.quantidade += saida.quantidade_saida
            saida.status_retorno = 'devolvido'

            # Histórico
            hist = HistoricoAcoes(
                data_acao=datetime.utcnow(),
                tipo_acao="Devolução de Material",
                detalhes=f"Item '{produto.nome}' (x{saida.quantidade_saida}) devolvido ao estoque.",
                solicitacao_id=solicitacao.id,
                usuario_id=current_user.id,
                produto_id=produto.id
            )
            db.session.add(hist)
            flash(f'{produto.nome} devolvido ao estoque com sucesso.', 'success')

        elif acao == 'consumir':
            saida.status_retorno = 'consumido'

            hist = HistoricoAcoes(
                data_acao=datetime.utcnow(),
                tipo_acao="Baixa Definitiva",
                detalhes=f"Item '{produto.nome}' (x{saida.quantidade_saida}) marcado como consumido/utilizado.",
                solicitacao_id=solicitacao.id,
                usuario_id=current_user.id,
                produto_id=produto.id
            )
            db.session.add(hist)
            flash(f'{produto.nome} marcado como consumido (não retornará).', 'info')

        elif acao == 'perda':
            saida.status_retorno = 'perdido'

            hist = HistoricoAcoes(
                data_acao=datetime.utcnow(),
                tipo_acao="Perda de Material",
                detalhes=f"Item '{produto.nome}' (x{saida.quantidade_saida}) registrado como PERDIDO/DANIFICADO.",
                solicitacao_id=solicitacao.id,
                usuario_id=current_user.id,
                produto_id=produto.id
            )
            db.session.add(hist)
            flash(f'{produto.nome} registrado como PERDA.', 'warning')

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar item: {str(e)}', 'error')

    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))


@app.route('/historico')
@login_required
def historico():
    todas_acoes = HistoricoAcoes.query.order_by(HistoricoAcoes.data_acao.desc()).limit(500).all()

    return render_template('historico.html', historico=todas_acoes)

@app.route('/historico/detalhes/<int:solicitacao_id>')
@login_required
def historico_detalhes(solicitacao_id):
    if not current_user.has_permission('gerenciar_solicitacoes'):
        flash('Você não tem permissão para ver os detalhes do histórico.', 'error')
        return redirect(url_for('historico'))

    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)

    return render_template('historico_detalhes.html', solicitacao=solicitacao, HistoricoAcoes=HistoricoAcoes)

@app.route('/historico_ativo', methods=['GET'])
@login_required
@permission_required('gerenciar_solicitacoes')
def historico_ativo():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int) 
    patrimonio_query = request.args.get('patrimonio', '').strip()
    
    solicitacoes = []
    pagination = None

    if patrimonio_query:
        chamados_via_produto = db.session.query(SaidaMaterial.solicitacao_id)\
                                           .join(Produto)\
                                           .filter(Produto.codigo_barras.ilike(f'%{patrimonio_query}%'))

        query = Solicitacao.query.filter(
            db.or_(
                Solicitacao.patrimonio_ativo.ilike(f'%{patrimonio_query}%'),
                Solicitacao.id.in_(chamados_via_produto)
            )
        ).order_by(Solicitacao.data_solicitacao.desc())
        
        pagination = db.paginate(query, per_page=per_page, page=page) 
        solicitacoes = pagination.items
    
    return render_template('historico_ativo.html', 
                           solicitacoes=solicitacoes, 
                           pagination=pagination,
                           patrimonio_query=patrimonio_query,
                           per_page=per_page) 

@app.route('/supervisao')
@login_required
@permission_required('admin')
def supervisao():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    chamado_id_filter = request.args.get('chamado_id', '').strip()
    codigo_item_filter = request.args.get('codigo_item', '').strip()
    usuario_id_filter = request.args.get('usuario_id', '').strip()

    query = HistoricoAcoes.query.options(
        joinedload(HistoricoAcoes.usuario), 
        joinedload(HistoricoAcoes.produto)
    )

    if chamado_id_filter:
        query = query.filter(HistoricoAcoes.solicitacao_id == chamado_id_filter)
    if usuario_id_filter:
        query = query.filter(HistoricoAcoes.usuario_id == usuario_id_filter)
    if codigo_item_filter:
        query = query.join(HistoricoAcoes.produto).filter(Produto.codigo_barras.ilike(f'%{codigo_item_filter}%'))
    pagination = db.paginate(
        query.order_by(HistoricoAcoes.data_acao.desc()), 
        per_page=per_page, 
        page=page
    )
    acoes = pagination.items

    usuarios = Usuario.query.order_by(Usuario.username).all()

    return render_template('supervisao.html', 
                           acoes=acoes, 
                           usuarios=usuarios, 
                           pagination=pagination,
                           chamado_id_filter=chamado_id_filter,
                           codigo_item_filter=codigo_item_filter,
                           usuario_id_filter=usuario_id_filter,
                           per_page=per_page)
@app.route('/supervisao/relatorio_pdf')
@login_required
@permission_required('admin')
def gerar_relatorio_supervisao_pdf():
    produtos = Produto.query.order_by(Produto.nome).all()
    report_data = []

    for produto in produtos:
        qtd_atual = produto.quantidade
        qtd_inicial = produto.quantidade_inicial

        if qtd_inicial > 0:
            percentual_uso = ((qtd_inicial - qtd_atual) / qtd_inicial) * 100
        else:
            percentual_uso = 0

        movimentos = HistoricoAcoes.query.filter_by(produto_id=produto.id).order_by(HistoricoAcoes.data_acao.asc()).all()

        report_data.append({
            'nome': produto.nome,
            'codigo_barras': produto.codigo_barras,
            'qtd_inicial': qtd_inicial,
            'qtd_atual': qtd_atual,
            'percentual_uso': round(percentual_uso, 2),
            'movimentos': movimentos
        })

    logo_path = os.path.join(basedir, 'static', 'dmttlogo.png')
    logo_base64 = convert_logo_to_base64(logo_path)
    data_emissao = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    rendered = render_template('supervisao_pdf.html',
                               report_data=report_data,
                               logo_base64=logo_base64,
                               data_emissao=data_emissao)

    pdf = pdfkit.from_string(rendered, False, configuration=pdfkit_config, options={'enable-local-file-access': True})
    return send_file(BytesIO(pdf), download_name=f'Relatorio_Supervisao_Itens.pdf', as_attachment=True)


@app.route('/download_anexo/<int:anexo_id>')
def download_anexo(anexo_id):
    try:
        anexo = Anexo.query.get_or_404(anexo_id)
        caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], anexo.nome_arquivo)

        if os.path.exists(caminho_arquivo):
            return send_from_directory(app.config['UPLOAD_FOLDER'], anexo.nome_arquivo, as_attachment=True)
        else:
            flash('Arquivo físico não encontrado no servidor.', 'error')
            return redirect(request.referrer or url_for('index'))

    except Exception as e:
        print(f"Erro no download: {e}")
        flash('Erro ao tentar baixar o arquivo.', 'error')
        return redirect(request.referrer or url_for('index'))

@app.route('/exibir_index')
def exibir_index():
    return redirect(url_for('login'))

@app.route('/exibir_login')
def exibir_login():
    return redirect(url_for('login'))

@scheduler.task('cron', id='job_limpeza_itens_zerados', hour=3, minute=30)
def limpeza_itens_zerados():
    """
    Esta tarefa é executada todos os dias às 03:30 da manhã.
    Ela busca por produtos com quantidade 0 que foram atualizados
    há mais de 7 dias e os exclui permanentemente.
    """
    with app.app_context():
        print("\n--- EXECUTANDO TAREFA AGENDADA: Limpeza de Itens Zerados ---")
        try:
            # Define o limite de tempo (7 dias atrás)
            limite_de_tempo = datetime.utcnow() - timedelta(days=7)

            produtos_zerados = Produto.query.filter(Produto.quantidade <= 0).all()
            
            produtos_excluidos_count = 0
            for produto in produtos_zerados:
                ultima_atualizacao = HistoricoAcoes.query.filter_by(produto_id=produto.id)\
                                                         .order_by(HistoricoAcoes.data_acao.desc())\
                                                         .first()

                if ultima_atualizacao and ultima_atualizacao.data_acao < limite_de_tempo:
                    nome_produto_excluido = produto.nome
                    id_produto_excluido = produto.id
                    print(f"-> Preparando para excluir produto '{nome_produto_excluido}' (ID: {id_produto_excluido})...")
                    
                    log_exclusao = HistoricoAcoes(
                        usuario_id=1, # Assume que o usuário 'admin' tem ID 1
                        tipo_acao='exclusao_automatica',
                        detalhes=f"Produto '{nome_produto_excluido}' excluído automaticamente por ter estoque 0 há mais de 7 dias.",
                        produto_id=id_produto_excluido
                    )
                    db.session.add(log_exclusao)
                    db.session.delete(produto)
                    produtos_excluidos_count += 1
            
            if produtos_excluidos_count > 0:
                db.session.commit()
                print(f"--- TAREFA CONCLUÍDA: {produtos_excluidos_count} produto(s) foram excluídos. ---\n")
            else:
                print("--- TAREFA CONCLUÍDA: Nenhum produto para excluir. ---\n")

        except Exception as e:
            db.session.rollback()
            print(f"--- ERRO NA TAREFA AGENDADA 'limpeza_itens_zerados': {e} ---\n")
            
def setup_database(app):
    """Garante que o banco de dados e as tabelas existam."""
    with app.app_context():
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        db_name = db.engine.url.database

        # Cria uma URI para conectar ao banco 'postgres' padrão para verificar se o nosso banco existe
        maintenance_uri = db.engine.url._replace(database='postgres')
        engine = create_engine(maintenance_uri)

        try:
            with engine.connect() as connection:
                print("✅ Conexão com o servidor PostgreSQL estabelecida.")
                
                # Verifica se o banco de dados existe
                result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
                db_exists = result.scalar() == 1

                if not db_exists:
                    print(f"AVISO: Banco de dados '{db_name}' não encontrado. Criando...")
                    # CREATE DATABASE não pode ser executado em um bloco de transação, por isso o 'COMMIT'
                    connection.execute(text("COMMIT"))
                    connection.execute(text(f'CREATE DATABASE "{db_name}"'))
                    print(f"✅ Banco de dados '{db_name}' criado com sucesso.")
                else:
                    print(f"✅ Banco de dados '{db_name}' já existe.")

                # Após garantir que o banco existe, aplica as migrações para criar as tabelas
                print("INFO: Aplicando migrações do banco de dados (se houver alguma pendente)...")
                migrations_dir = os.path.join(basedir, 'migrations')
                upgrade(directory=migrations_dir)
                print("✅ Migrações aplicadas com sucesso. As tabelas estão prontas.")

        except OperationalError as e:
            print("❌ ERRO CRÍTICO: Não foi possível conectar ao servidor PostgreSQL.")
            print("   Verifique se o servidor está no ar, o IP e a senha estão corretos no config.py.")
            print(f"   Erro: {e}")
            return False
        except Exception as e:
            print(f"❌ ERRO CRÍTICO inesperado durante a configuração do banco de dados: {e}")
            return False
            
    return True

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/solicitacao/<int:solicitacao_id>/upload_foto', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def upload_foto(solicitacao_id):
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)

    if 'foto' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

    file = request.files['foto']
    tipo_anexo = request.form.get('tipo_anexo') 

    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'warning')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"

        try:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))

            novo_anexo = Anexo(
                nome_arquivo=unique_filename,
                tipo_anexo=tipo_anexo,
                solicitacao_id=solicitacao.id
            )
            db.session.add(novo_anexo)

            historico_upload = HistoricoAcoes(
                solicitacao_id=solicitacao.id,
                usuario_id=current_user.id,
                tipo_acao='foto_adicionada',
                detalhes=f"Foto de '{tipo_anexo}' adicionada ao chamado: {original_filename}"
            )
            db.session.add(historico_upload)

            db.session.commit()
            flash(f'Foto de "{tipo_anexo}" enviada com sucesso!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar a foto ou registrar no banco: {e}', 'error')

    else:
        flash('Tipo de arquivo não permitido. Apenas PNG, JPG, JPEG e GIF.', 'error')

    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao.id))

@app.route('/anexo/<int:anexo_id>/excluir', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def excluir_anexo(anexo_id):
    anexo = Anexo.query.get_or_404(anexo_id)
    solicitacao_id = anexo.solicitacao_id
    
    try:
        caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], anexo.nome_arquivo)
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
        
        historico_exclusao = HistoricoAcoes(
            solicitacao_id=solicitacao_id,
            usuario_id=current_user.id,
            tipo_acao='foto_excluida',
            detalhes=f"Foto de '{anexo.tipo_anexo}' excluída do chamado: {anexo.nome_arquivo}"
        )
        db.session.add(historico_exclusao)
        
        db.session.delete(anexo)
        
        db.session.commit()
        flash('Foto excluída com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir a foto: {e}', 'error')
        
    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))


if __name__ == '__main__':
    if setup_database(app):
        # Cria o usuário admin padrão, se não existir
        with app.app_context():
            if not Usuario.query.filter_by(username='admin').first():
                admin = Usuario(username='admin', dados='Admin TI', tipo_usuario='admin')
                admin.set_password('dmtt2026ti')
                db.session.add(admin)
                db.session.commit()
                print("✅ Usuário 'admin' padrão criado com sucesso.")
        
        print("🚀 Iniciando a aplicação Flask...")
        app.run(host='0.0.0.0', port=8080, debug=False)
