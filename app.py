from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file, session
import pdfkit
from io import BytesIO
from db_setup import db
from models import Produto, Setor, Solicitacao, Usuario, SaidaMaterial, Comentario
from sqlalchemy.orm import Session
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

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

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

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def setup_database(app):
    """
    Verifica se o banco de dados e as tabelas existem.
    Se não existirem, cria o banco e as tabelas.
    """
    with app.app_context():
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        parsed_uri = urlparse(db_uri)
        db_name = parsed_uri.path[1:]
        postgres_uri = f"postgresql://{parsed_uri.username}:{parsed_uri.password}@{parsed_uri.hostname}:{parsed_uri.port}/postgres"
        
        engine = create_engine(postgres_uri)

        try:
            with engine.connect() as connection:
                connection.execution_options(isolation_level="AUTOCOMMIT")
                result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"))
                db_exists = result.scalar() == 1

                if not db_exists:
                    print(f"O banco de dados '{db_name}' não existe. Criando...")
                    connection.execute(text(f'CREATE DATABASE "{db_name}"'))
                    print(f"Banco de dados '{db_name}' criado com sucesso.")
                else:
                    print(f"O banco de dados '{db_name}' já existe.")
        except (OperationalError, ProgrammingError) as e:
            print(f"ERRO: Não foi possível verificar ou criar o banco de dados.")
            print(f"Verifique se o servidor PostgreSQL está rodando e se as credenciais em config.py estão corretas.")
            print(f"Erro original: {e}")
            return
        print("Verificando e criando tabelas, se necessário...")
        db.create_all()
        print("Setup do banco de dados concluído. Tabelas estão prontas.")


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
    
def to_localtime(utc_datetime):
    if not utc_datetime:
        return ""
    local_tz = pytz.timezone('America/Maceio') # Fuso horário de Alagoas
    local_dt = utc_datetime.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return local_dt.strftime('%d/%m/%Y às %H:%M')

app.jinja_env.filters['localtime'] = to_localtime

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
        
        # Evita cadastrar código de barras vazio como único
        produto_existente = None
        if codigo_barras:
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

# FUNÇÃO CORRIGIDA
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
            produto.tipo_item = request.form['tipo_item'] # Agora este campo virá do formulário
            db.session.commit()
            flash('Item/Produto atualizado com sucesso!', 'success')
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar: {e}', 'error')
    return render_template('atualizar.html', produto=produto)

# --- ROTAS DE SOLICITAÇÕES ---
@app.route('/portal_solicitacoes', methods=['GET', 'POST'])
@login_required
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
                data_solicitacao=datetime.utcnow() 
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
    now = datetime.utcnow()
    limite_de_tempo = now - timedelta(minutes=1)
    solicitacoes_visiveis = Solicitacao.query.filter(
        db.or_(
            Solicitacao.status.in_(['pendente', 'aprovada']),
            db.and_(
                Solicitacao.status.in_(['entregue', 'rejeitada', 'excluido']),
                Solicitacao.data_atualizacao.isnot(None),
                Solicitacao.data_atualizacao > limite_de_tempo
            )
        )
    ).order_by(Solicitacao.data_solicitacao.desc()).all()
    
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

# NOVO CÓDIGO - 
@app.route('/excluir_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def excluir_solicitacao(solicitacao_id):
    try:
        solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
        
        # Em vez de deletar, mudamos o status e a data de atualização
        solicitacao.status = 'excluido'
        solicitacao.data_atualizacao = datetime.utcnow()
        
        db.session.commit()
        flash(f'Chamado #{solicitacao.id} foi movido para a lixeira.', 'success')
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
                quantidade_saida=item['quantidade_saida']
            )
            db.session.add(nova_saida)
            
        db.session.commit()
        flash(f'{len(itens_para_adicionar)} tipo(s) de item(ns) adicionado(s) ao chamado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao salvar os itens: {e}', 'error')

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
    logo_base64 = convert_logo_to_base64('static/dmttlogo.png')
    rendered = render_template('saida_pdf.html', 
                               solicitacao=solicitacao,
                               produtos=produtos_para_pdf,
                               data_pedido=data_hora, 
                               logo_base64=logo_base64)
    pdf = pdfkit.from_string(rendered, False, configuration=pdfkit_config, options={'enable-local-file-access': None})
    return send_file(BytesIO(pdf), download_name=f'Requisicao_Chamado_{solicitacao.id}.pdf', as_attachment=True)

@app.route('/solicitacao/<int:solicitacao_id>/confirmar_devolucao', methods=['POST'])
@login_required
@permission_required('saida_produto') 
def confirmar_devolucao_itens(solicitacao_id):
    ids_das_saidas_retornadas = request.form.getlist('saida_id')
    if not ids_das_saidas_retornadas:
        flash('Nenhum item retornável foi selecionado para devolução.', 'warning')
        return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

    itens_processados = 0
    try:
        for saida_id in ids_das_saidas_retornadas:
            saida_material = SaidaMaterial.query.get(saida_id)
            if saida_material and saida_material.solicitacao_id == solicitacao_id and not saida_material.retornado:
                produto = saida_material.produto
                produto.quantidade += saida_material.quantidade_saida
                saida_material.retornado = True
                db.session.add(produto)
                db.session.add(saida_material)
                itens_processados += 1

        db.session.commit()
        if itens_processados > 0:
            flash(f'{itens_processados} item(ns) retornado(s) ao estoque com sucesso!', 'success')
        else:
            flash('Os itens selecionados já haviam sido retornados anteriormente.', 'info')
            
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
            novo_usuario = Usuario(
                username=username,
                dados=dados,
                tipo_usuario=tipo_usuario
            )
            novo_usuario.set_password(password)
            db.session.add(novo_usuario)
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

# FUNÇÃO CORRIGIDA
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

        # Verifica se o novo username já está em uso por outro usuário
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
        return redirect(url_for('dashboard'))
        
    if current_user.id == usuario_id:
        flash('Você não pode excluir seu próprio usuário.', 'error')
        return redirect(url_for('lista_usuarios'))
        
    try:
        usuario_para_excluir = Usuario.query.get_or_404(usuario_id)
        db.session.delete(usuario_para_excluir)
        db.session.commit()
        flash(f'Usuário "{usuario_para_excluir.username}" foi excluído permanentemente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir usuário: {e}', 'error')
        
    return redirect(url_for('lista_usuarios'))

@app.route('/lista_solicitacoes')
def lista_solicitacoes():
    """
    Exibe uma lista pública de chamados recentes com filtros inteligentes.
    """
    now = datetime.utcnow()
    rejeitadas_excluidas_limite = now - timedelta(hours=2)
    concluidas_limite = now - timedelta(hours=4)
    solicitacoes_visiveis = Solicitacao.query.filter(
        db.or_(
            Solicitacao.status.in_(['pendente', 'aprovada']),
            db.and_(
                Solicitacao.status.in_(['rejeitada', 'excluido']),
                Solicitacao.data_atualizacao.isnot(None),
                Solicitacao.data_atualizacao > rejeitadas_excluidas_limite
            ),
            db.and_(
                Solicitacao.status == 'entregue',
                Solicitacao.data_atualizacao.isnot(None),
                Solicitacao.data_atualizacao > concluidas_limite
            )
        )
    ).order_by(Solicitacao.data_solicitacao.desc()).all()

    return render_template('lista_solicitacoes.html', solicitacoes=solicitacoes_visiveis)

@app.route('/historico')
@login_required
def historico():
    if not current_user.has_permission('gerenciar_solicitacoes'):
        flash('Você não tem permissão para acessar o histórico completo.', 'error')
        return redirect(url_for('dashboard'))

    todos_os_chamados = Solicitacao.query.order_by(Solicitacao.data_solicitacao.desc()).all()
    
    return render_template('historico.html', solicitacoes=todos_os_chamados)

@app.route('/historico/detalhes/<int:solicitacao_id>')
@login_required
def historico_detalhes(solicitacao_id):
    # Apenas usuários com permissão podem ver os detalhes.
    if not current_user.has_permission('gerenciar_solicitacoes'):
        flash('Você não tem permissão para ver os detalhes do histórico.', 'error')
        return redirect(url_for('historico'))

    # Busca o chamado específico pelo ID ou retorna um erro 404 se não encontrar.
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)

    return render_template('historico_detalhes.html', solicitacao=solicitacao)

@app.route('/exibir_index')
def exibir_index():
    return redirect(url_for('login'))

@app.route('/exibir_login')
def exibir_login():
    return redirect(url_for('login'))

if __name__ == '__main__':
    setup_database(app)
    with app.app_context():
        db.create_all()

        if not Usuario.query.filter_by(username='admin').first():
            admin = Usuario(username='admin', dados='Admin TI', tipo_usuario='admin')
            admin.set_password('Admin_ti@')  # Altere para uma senha segura
            db.session.add(admin)
            db.session.commit()
            print("Usuário 'admin' criado com a senha 'Admin_ti@'")
    
    app.run(host='0.0.0.0', port=8080, debug=False)