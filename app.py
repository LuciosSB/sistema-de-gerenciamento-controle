from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file, session
import pdfkit
from io import BytesIO
from db_setup import db
from models import Produto, Setor, Solicitacao, Usuario
from sqlalchemy.orm import Session
import json
from datetime import datetime
import base64
import os
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import Config

app = Flask(__name__)
app.config.from_object(Config) # Carrega todas as configurações do config.py

# Conecta a instância do SQLAlchemy com a aplicação Flask
db.init_app(app)

pdfkit_config = pdfkit.configuration(wkhtmltopdf=app.config['WKHTMLTOPDF_PATH'])

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def permission_required(permission):
    """
    Decorator para verificar se o usuário tem a permissão necessária
    """
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
    """
    Converte uma imagem para base64 para incorporar no HTML
    """
    try:
        # Verificar se o arquivo existe
        if not os.path.exists(image_path):
            # Tentar diferentes caminhos possíveis
            possible_paths = [
                'static/logodmtt.png',
                'static/dmttlogo.png',
                'logodmtt.png',
                'dmttlogo.png'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    image_path = path
                    break
            else:
                return None
            
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            base64_string = base64.b64encode(image_data).decode('utf-8')
            
            # Verificar se é uma string base64 válida
            try:
                base64.b64decode(base64_string)
                return base64_string
            except Exception:
                return None
                
    except Exception:
        return None

# Opção alternativa: definir a logo diretamente como string base64
LOGO_BASE64_HARDCODED = ""

@app.route('/')
def index():
    """
    Página inicial - redireciona diretamente para login
    """
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Página de login
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Username e senha são obrigatórios.', 'error')
            return render_template('login.html')
        
        # Buscar usuário
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.check_password(password) and usuario.ativo:
            login_user(usuario)
            flash(f'Bem-vindo, {usuario.username}!', 'success')
            
            # Redirecionar para a página solicitada ou dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Username ou senha incorretos, ou usuário inativo.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """
    Logout do usuário
    """
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard principal baseado no tipo de usuário
    """
    user_type = current_user.tipo_usuario
    
    # Estatísticas básicas
    total_produtos = Produto.query.count()
    total_solicitacoes = Solicitacao.query.count()
    solicitacoes_pendentes = Solicitacao.query.filter_by(status='pendente').count()
    
    return render_template('dashboard.html', 
                         user_type=user_type,
                         total_produtos=total_produtos,
                         total_solicitacoes=total_solicitacoes,
                         solicitacoes_pendentes=solicitacoes_pendentes)

@app.route('/cadastro', methods=['GET', 'POST'])
@login_required
@permission_required('cadastrar_produto')
def cadastro_produto():
    """
    Cadastro de produtos - apenas para almoxarifado
    """
    if request.method == 'POST':
        codigo_barras = request.form['codigo_barras']
        nome = request.form['nome']
        quantidade = request.form['quantidade']
        
        # Verificar se o código de barras já exists
        produto_existente = Produto.query.filter_by(codigo_barras=codigo_barras).first()
        if produto_existente:
            flash('Código de barras já cadastrado!', 'error')
            return render_template('cadastro.html')
        
        try:
            produto = Produto(
                codigo_barras=codigo_barras,
                nome=nome,
                quantidade=int(quantidade)
            )
            db.session.add(produto)
            db.session.commit()
            flash('Produto cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao cadastrar produto. Tente novamente.', 'error')
    
    return render_template('cadastro.html')

@app.route('/produtos')
@login_required
@permission_required('listar_produtos')
def listar_produtos():
    """
    Listagem de produtos
    """
    produtos = Produto.query.all()
    return render_template('produtos.html', produtos=produtos)

@app.route('/portal_solicitacoes', methods=['GET', 'POST'])
def portal_solicitacoes():
    """
    Portal de solicitações onde usuários podem fazer pedidos de equipamentos
    AGORA SEM NECESSIDADE DE LOGIN
    """
    if request.method == 'POST':
        try:
            # Coletar dados do formulário
            nome_solicitante = request.form.get('nome_solicitante', '').strip()
            setor = request.form.get('setor', '').strip()
            nome_item = request.form.get('nome_item', '').strip()
            quantidade = request.form.get('quantidade', '').strip()
            descricao = request.form.get('descricao', '').strip()
            
            # Validações básicas
            if not nome_solicitante or not setor or not nome_item or not quantidade:
                flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
                return redirect(url_for('portal_solicitacoes'))
            
            try:
                quantidade = int(quantidade)
                if quantidade < 1:
                    flash('A quantidade deve ser pelo menos 1.', 'error')
                    return redirect(url_for('portal_solicitacoes'))
            except ValueError:
                flash('Quantidade deve ser um número válido.', 'error')
                return redirect(url_for('portal_solicitacoes'))
            
            # Criar nova solicitação
            nova_solicitacao = Solicitacao(
                nome_solicitante=nome_solicitante,
                setor=setor,
                nome_item=nome_item,
                quantidade=quantidade,
                descricao=descricao if descricao else None,
                status='pendente',
                data_solicitacao=datetime.now()
            )
            
            db.session.add(nova_solicitacao)
            db.session.commit()
            
            flash('Solicitação enviada com sucesso! Aguarde aprovação.', 'success')
            return redirect(url_for('portal_solicitacoes'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro interno. Tente novamente mais tarde.', 'error')
            return redirect(url_for('portal_solicitacoes'))
    
    # GET: Exibir formulário 
    try:
        # Mostrar apenas as últimas 5 solicitações como exemplo público
        solicitacoes = Solicitacao.query.order_by(Solicitacao.data_solicitacao.desc()).limit(5).all()
        
        return render_template('portal_solicitacoes.html', solicitacoes=solicitacoes, public_access=True)
    except Exception as e:
        return render_template('portal_solicitacoes.html', solicitacoes=[], public_access=True)

@app.route('/gerenciar_solicitacoes')
@login_required
@permission_required('gerenciar_solicitacoes')
def gerenciar_solicitacoes():
    """
    Gerenciar solicitações (área administrativa)
    """
    try:
        # Buscar todas as solicitações ordenadas por data (mais recentes primeiro)
        solicitacoes = Solicitacao.query.order_by(Solicitacao.data_solicitacao.desc()).all()
        
        return render_template('gerenciar_solicitacoes.html', solicitacoes=solicitacoes)
        
    except Exception as e:
        flash('Erro ao carregar solicitações. Tente novamente.', 'error')
        return render_template('gerenciar_solicitacoes.html', solicitacoes=[])

@app.route('/gerenciar_solicitacoes/<int:solicitacao_id>')
@login_required
@permission_required('gerenciar_solicitacoes')
def gerenciar_solicitacoes_detalhes(solicitacao_id):
    """
    Detalhes de uma solicitação específica
    """
    try:
        solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
        return render_template('gerenciar_solicitacoes_detalhes.html', solicitacao=solicitacao)
        
    except Exception as e:
        flash('Erro ao carregar detalhes da solicitação.', 'error')
        return redirect(url_for('gerenciar_solicitacoes'))

@app.route('/atualizar_status_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def atualizar_status_solicitacao(solicitacao_id):
    """
    Atualizar o status de uma solicitação
    """
    try:
        solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
        
        novo_status = request.form.get('status')
        
        # Validar se o status é válido
        status_validos = ['pendente', 'aprovada', 'rejeitada', 'entregue']
        if novo_status not in status_validos:
            flash('Status inválido.', 'error')
            return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))
        
        # Atualizar o status
        solicitacao.status = novo_status
        solicitacao.data_atualizacao = datetime.now()
        
        db.session.commit()
        
        # Mensagem de sucesso personalizada baseada no status
        mensagens_status = {
            'pendente': 'Solicitação marcada como PENDENTE',
            'aprovada': 'Solicitação APROVADA com sucesso',
            'rejeitada': 'Solicitação REJEITADA',
            'entregue': 'Solicitação marcada como ENTREGUE'
        }
        
        flash(f'{mensagens_status.get(novo_status, "Status atualizado")} para solicitação #{solicitacao_id}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao atualizar status da solicitação.', 'error')
    
    return redirect(url_for('gerenciar_solicitacoes_detalhes', solicitacao_id=solicitacao_id))

@app.route('/excluir_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
@permission_required('gerenciar_solicitacoes')
def excluir_solicitacao(solicitacao_id):
    """
    Excluir uma solicitação
    """
    try:
        solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
        
        db.session.delete(solicitacao)
        db.session.commit()
        
        flash(f'Solicitação #{solicitacao_id} excluída com sucesso.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir solicitação.', 'error')
    
    return redirect(url_for('gerenciar_solicitacoes'))

@app.route('/saida', methods=['GET', 'POST'])
@login_required
@permission_required('saida_produto')
def saida_produto():
    """
    Registro de saída de produtos
    """
    setores = Setor.query.all()
    success_message = "Saída com sucesso"
    error_message = "Alguns produtos solicitados não estão com estoque suficiente"
    produtos_para_corrigir = []
    produtos_para_pdf = []

    if request.method == 'POST':
        # Verificar se é novo setor ou setor existente
        novo_setor = request.form.get('novo_setor')
        setor_selecionado = request.form.get('setor_id')
        edificio = request.form.get('edificio')
        
        produto_ids = request.form.getlist('produto_id[]')
        quantidades_saida = request.form.getlist('quantidade_saida[]')

        # Validar se pelo menos um produto foi selecionado
        if not produto_ids or not any(produto_ids):
            return render_template(
                'saida.html',
                produtos=Produto.query.all(),
                setores=setores,
                error="Por favor, selecione pelo menos um produto.",
                produtos_para_corrigir=[]
            )

        erros_encontrados = False
        setor = None
        setor_nome = ""
        data_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        # Determinar qual setor usar
        if novo_setor and novo_setor.strip():
            setor_nome = novo_setor.strip()
            setor_existente = Setor.query.filter_by(nome=setor_nome).first()
            if setor_existente:
                setor = setor_existente
            else:
                setor = Setor(nome=setor_nome)
                db.session.add(setor)
                db.session.flush()
        elif setor_selecionado:
            setor_nome = setor_selecionado
            setor_existente = Setor.query.filter_by(nome=setor_nome).first()
            if setor_existente:
                setor = setor_existente
            else:
                setor = Setor(nome=setor_nome)
                db.session.add(setor)
                db.session.flush()
        else:
            return render_template(
                'saida.html',
                produtos=Produto.query.all(),
                setores=setores,
                error="Por favor, selecione um setor ou crie um novo.",
                produtos_para_corrigir=[]
            )

        # Processar produtos
        for produto_id, quantidade_saida in zip(produto_ids, quantidades_saida):
            if not produto_id or not quantidade_saida:
                continue
                
            produto = Produto.query.get(produto_id)
            quantidade_saida = int(quantidade_saida)

            if produto and produto.quantidade >= quantidade_saida:
                produto.quantidade -= quantidade_saida
                produtos_para_pdf.append({
                    'codigo_barras': produto.codigo_barras,
                    'nome': produto.nome,
                    'quantidade_solicitada': quantidade_saida
                })
            else:
                produtos_para_corrigir.append({
                    'id': produto.id if produto else None,
                    'nome': produto.nome if produto else 'Desconhecido',
                    'quantidade': quantidade_saida,
                    'quantidade_atual': produto.quantidade if produto else 0
                })
                erros_encontrados = True

        if not erros_encontrados and produtos_para_pdf:
            db.session.commit()
            
            # Tentar carregar a logo do arquivo primeiro
            logo_base64 = convert_logo_to_base64('static/logodmtt.png')
            
            # Se não conseguir carregar do arquivo, usar a versão hardcoded (se disponível)
            if not logo_base64 and LOGO_BASE64_HARDCODED.strip():
                logo_clean = LOGO_BASE64_HARDCODED.strip().replace('\n', '').replace('\r', '').replace(' ', '')
                
                try:
                    base64.b64decode(logo_clean)
                    logo_base64 = logo_clean
                except Exception:
                    logo_base64 = None
            
            # Gerar o PDF automaticamente após o commit
            rendered = render_template('saida_pdf.html', 
                                       produtos=produtos_para_pdf,
                                       setor=setor_nome,
                                       data_pedido=data_hora,
                                       logo_base64=logo_base64,
                                       usuario=current_user.username)
            
            # Configurações otimizadas para wkhtmltopdf com imagens base64
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': 'UTF-8',
                'no-outline': None,
                'enable-local-file-access': None,
                'disable-smart-shrinking': None,
                'enable-javascript': None,
                'javascript-delay': 2000,
                'load-error-handling': 'ignore',
                'load-media-error-handling': 'ignore',
                'print-media-type': None,
                'disable-external-links': None,
                'disable-internal-links': None,
            }
            
            try:
                pdf = pdfkit.from_string(rendered, False, configuration=pdfkit_config, options=options)
                
                if not pdf:
                    return "Erro na geração do PDF", 500
                
                return send_file(BytesIO(pdf), download_name=f'Requisição - Setor {setor_nome}.pdf', as_attachment=True)
                
            except Exception as e:
                return f"Erro na geração do PDF: {str(e)}", 500
        
        elif erros_encontrados:
            db.session.rollback()
            return render_template(
                'saida.html',
                produtos=Produto.query.all(),
                setores=setores,
                error=error_message,
                produtos_para_corrigir=produtos_para_corrigir
            )
        else:
            return render_template(
                'saida.html',
                produtos=Produto.query.all(),
                setores=setores,
                error="Nenhum produto válido foi selecionado.",
                produtos_para_corrigir=[]
            )

    return render_template(
        'saida.html',
        produtos=Produto.query.all(),
        setores=setores,
        produtos_para_corrigir=[]
    )

@app.route('/quantidade_produto/<int:produto_id>', methods=['GET'])
@login_required
def quantidade_produto(produto_id):
    """
    Retorna a quantidade disponível de um produto (AJAX)
    """
    produto = Produto.query.get(produto_id)
    
    if produto:
        return jsonify({'quantidade': produto.quantidade})
    return jsonify({'quantidade': 0})

@app.route('/atualizar', methods=['GET', 'POST'])
@login_required
@permission_required('atualizar_produto')
def selecionar_produto_atualizar():
    """
    Seleção de produto para atualização
    """
    if request.method == 'POST':
        produto_id = request.form['produto_id']
        return redirect(url_for('atualizar_produto', produto_id=produto_id))
    
    produtos = Produto.query.all()
    return render_template('selecionar_produto.html', produtos=produtos)

@app.route('/atualizar/<int:produto_id>', methods=['GET', 'POST'])
@login_required
@permission_required('atualizar_produto')
def atualizar_produto(produto_id):
    """
    Atualização de produto específico
    """
    produto = Produto.query.get_or_404(produto_id)

    if request.method == 'POST':
        try:
            codigo_barras = request.form['codigo_barras']
            
            # Verificar se o código de barras já existe em outro produto
            produto_existente = Produto.query.filter(
                Produto.codigo_barras == codigo_barras,
                Produto.id != produto_id
            ).first()
            
            if produto_existente:
                flash('Código de barras já está sendo usado por outro produto!', 'error')
                return render_template('atualizar.html', produto=produto)
            
            produto.codigo_barras = codigo_barras
            produto.nome = request.form['nome']
            produto.quantidade = int(request.form['quantidade'])
            
            db.session.commit()
            flash('Produto atualizado com sucesso!', 'success')
            return redirect(url_for('listar_produtos'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar produto. Tente novamente.', 'error')

    return render_template('atualizar.html', produto=produto)

# Rota para exibir o formulário de cadastro de usuário
@app.route('/cadastro_usuario', methods=['GET', 'POST'])
@login_required
def cadastro_usuario():
    """
    Página de cadastro de novo usuário (apenas para administradores)
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            username = request.form['username'].strip()
            dados = request.form['dados'].strip()
            password = request.form['password']
            tipo_usuario = request.form['tipo_usuario']
            
            # Validações
            if not username or not dados or not password or not tipo_usuario:
                flash('Todos os campos são obrigatórios!', 'error')
                return render_template('cadastro_usuario.html')
            
            if len(username) < 3:
                flash('Username deve ter pelo menos 3 caracteres!', 'error')
                return render_template('cadastro_usuario.html')
            
            if len(password) < 6:
                flash('Senha deve ter pelo menos 6 caracteres!', 'error')
                return render_template('cadastro_usuario.html')
            
            if tipo_usuario not in ['admin','almoxarifado', 'usuario_padrao', 'usuario_solicitante']:
                flash('Tipo de usuário inválido!', 'error')
                return render_template('cadastro_usuario.html')
            
            # Verificar se o username já existe
            if Usuario.query.filter_by(username=username).first():
                flash('Username já existe!', 'error')
                return render_template('cadastro_usuario.html')
            
            # Verificar se os dados já existem
            if Usuario.query.filter_by(dados=dados).first():
                flash('Dados já estão cadastrados!', 'error')
                return render_template('cadastro_usuario.html')
            
            # Criar novo usuário
            novo_usuario = Usuario(
                username=username,
                dados=dados,
                tipo_usuario=tipo_usuario,
                ativo=True  # Por padrão, usuário criado ativo
            )
            novo_usuario.set_password(password)
            
            db.session.add(novo_usuario)
            db.session.commit()
            
            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('lista_usuarios'))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar usuário. Tente novamente.', 'error')
    
    return render_template('cadastro_usuario.html')

# Rota para listar todos os usuários
@app.route('/lista_usuarios')
@login_required
def lista_usuarios():
    """
    Página com listagem de todos os usuários (apenas para administradores)
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    usuarios = Usuario.query.all()
    return render_template('lista_usuarios.html', usuarios=usuarios)


@app.route('/detalhes_usuario/<int:usuario_id>')
@login_required
def detalhes_usuario(usuario_id):
    """
    Página com detalhes completos de um usuário específico (apenas para administradores)
    Exibe informações do usuário e botões para ações (editar, excluir, etc.)
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Verificar se é o próprio usuário logado (para mostrar avisos diferentes)
    is_self = usuario.id == current_user.id
    
    # Verificar se é o último admin ativo (para controlar botões de exclusão/desativação)
    is_last_admin = False
    if usuario.tipo_usuario == 'admin' and usuario.ativo:
        total_admins_ativos = Usuario.query.filter_by(tipo_usuario='admin', ativo=True).count()
        is_last_admin = total_admins_ativos <= 1
    
    return render_template('detalhes_usuario.html', 
                         usuario=usuario, 
                         is_self=is_self, 
                         is_last_admin=is_last_admin)


@app.route('/atualizar_cadastro/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
def atualizar_cadastro(usuario_id):
    """
    Página para atualizar dados de usuário (apenas para administradores)
    GET - Exibe formulário preenchido com dados atuais
    POST - Processa a atualização dos dados
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Impedir que o usuário edite a si mesmo
    if usuario.id == current_user.id:
        flash('Você não pode editar seu próprio usuário.', 'warning')
        return redirect(url_for('detalhes_usuario', usuario_id=usuario_id))
    
    if request.method == 'POST':
        try:
            # Capturar dados do formulário
            username = request.form['username'].strip()
            dados = request.form['dados'].strip()
            tipo_usuario = request.form['tipo_usuario']
            ativo = 'ativo' in request.form
            nova_senha = request.form.get('nova_senha', '').strip()
            
            # Validações
            if not username:
                flash('Username é obrigatório.', 'error')
                return render_template('atualizar_cadastro.html', usuario=usuario)
            
            if not dados:
                flash('Dados são obrigatórios.', 'error')
                return render_template('atualizar_cadastro.html', usuario=usuario)
            
            # Verificar se o username já existe (exceto o próprio usuário)
            username_existente = Usuario.query.filter(
                Usuario.username == username,
                Usuario.id != usuario_id
            ).first()
            
            if username_existente:
                flash('Username já existe!', 'error')
                return render_template('atualizar_cadastro.html', usuario=usuario)
            
            # Verificar se os dados já existem (exceto o próprio usuário)
            dados_existentes = Usuario.query.filter(
                Usuario.dados == dados,
                Usuario.id != usuario_id
            ).first()
            
            if dados_existentes:
                flash('Dados já estão cadastrados!', 'error')
                return render_template('atualizar_cadastro.html', usuario=usuario)
            
            # Verificar se está tentando desativar o último admin
            if not ativo and usuario.tipo_usuario == 'admin' and usuario.ativo:
                total_admins_ativos = Usuario.query.filter_by(tipo_usuario='admin', ativo=True).count()
                if total_admins_ativos <= 1:
                    flash('Não é possível desativar o último administrador ativo.', 'error')
                    return render_template('atualizar_cadastro.html', usuario=usuario)
            
            # Atualizar dados do usuário
            usuario.username = username
            usuario.dados = dados
            usuario.tipo_usuario = tipo_usuario
            usuario.ativo = ativo
            
            # Atualizar senha se fornecida
            if nova_senha:
                if len(nova_senha) < 6:
                    flash('A nova senha deve ter pelo menos 6 caracteres.', 'error')
                    return render_template('atualizar_cadastro.html', usuario=usuario)
                usuario.set_password(nova_senha)
            
            db.session.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('detalhes_usuario', usuario_id=usuario.id))
            
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar usuário. Tente novamente.', 'error')
            print(f"Erro ao atualizar usuário: {e}")
    
    return render_template('atualizar_cadastro.html', usuario=usuario)


@app.route('/excluir_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def excluir_usuario(usuario_id):
    """
    Exclusão de usuário (apenas para administradores)
    Pode ser chamada dos detalhes do usuário ou da lista
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        usuario = Usuario.query.get_or_404(usuario_id)
        
        # Impedir que o usuário exclua a si mesmo
        if usuario.id == current_user.id:
            flash('Você não pode excluir seu próprio usuário.', 'error')
            return redirect(url_for('lista_usuarios'))
        
        # Verificar se é o último usuário admin ativo
        if usuario.tipo_usuario == 'admin' and usuario.ativo:
            total_admins_ativos = Usuario.query.filter_by(tipo_usuario='admin', ativo=True).count()
            if total_admins_ativos <= 1:
                flash('Não é possível excluir o último administrador ativo.', 'error')
                return redirect(url_for('lista_usuarios'))
        
        username_excluido = usuario.username
        db.session.delete(usuario)
        db.session.commit()
        
        flash(f'Usuário {username_excluido} excluído com sucesso.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir usuário.', 'error')
        print(f"Erro ao excluir usuário: {e}")
    
    return redirect(url_for('lista_usuarios'))


@app.route('/toggle_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def toggle_usuario(usuario_id):
    """
    Ativar/Desativar usuário rapidamente (apenas para administradores)
    Pode ser usado na lista de usuários para ação rápida
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        usuario = Usuario.query.get_or_404(usuario_id)
        
        # Impedir que o usuário desative a si mesmo
        if usuario.id == current_user.id:
            flash('Você não pode alterar o status do seu próprio usuário.', 'error')
            return redirect(url_for('lista_usuarios'))
        
        # Se está tentando desativar um admin, verificar se não é o último ativo
        if usuario.ativo and usuario.tipo_usuario == 'admin':
            total_admins_ativos = Usuario.query.filter_by(tipo_usuario='admin', ativo=True).count()
            if total_admins_ativos <= 1:
                flash('Não é possível desativar o último administrador ativo.', 'error')
                return redirect(url_for('lista_usuarios'))
        
        usuario.ativo = not usuario.ativo
        db.session.commit()
        
        status = 'ativado' if usuario.ativo else 'desativado'
        flash(f'Usuário {usuario.username} {status} com sucesso.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao alterar status do usuário.', 'error')
        print(f"Erro ao alterar status do usuário: {e}")
    
    # Verificar de onde veio a requisição para fazer o redirect correto
    referrer = request.form.get('redirect_to', 'lista_usuarios')
    if referrer == 'detalhes':
        return redirect(url_for('detalhes_usuario', usuario_id=usuario_id))
    else:
        return redirect(url_for('lista_usuarios'))


@app.route('/resetar_senha/<int:usuario_id>', methods=['POST'])
@login_required
def resetar_senha(usuario_id):
    """
    Resetar senha do usuário (apenas para administradores)
    Chamada exclusivamente dos detalhes do usuário
    """
    if current_user.tipo_usuario != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        usuario = Usuario.query.get_or_404(usuario_id)
        nova_senha = request.form.get('nova_senha', '').strip()
        
        if not nova_senha:
            flash('Nova senha é obrigatória.', 'error')
            return redirect(url_for('detalhes_usuario', usuario_id=usuario_id))
        
        if len(nova_senha) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'error')
            return redirect(url_for('detalhes_usuario', usuario_id=usuario_id))
        
        usuario.set_password(nova_senha)
        db.session.commit()
        
        flash(f'Senha do usuário {usuario.username} resetada com sucesso.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Erro ao resetar senha do usuário.', 'error')
        print(f"Erro ao resetar senha: {e}")
    
    return redirect(url_for('detalhes_usuario', usuario_id=usuario_id))

# Rotas para compatibilidade com templates antigos
@app.route('/exibir_index')
def exibir_index():
    return redirect(url_for('login'))

@app.route('/exibir_login')
def exibir_login():
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Criar usuário admin padrão se não existir
        admin = Usuario.query.filter_by(username='admin').first()
        if not admin:
            admin = Usuario(
                username='admin',
                dados='Admin TI',
                tipo_usuario='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Usuário admin criado com sucesso!")
            print("Username: admin")
            print("Password: admin123")
    
    app.run(host='0.0.0.0', port=5000, debug=True)