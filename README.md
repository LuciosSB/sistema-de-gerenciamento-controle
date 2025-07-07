# Sistema de Gestão de Manutenção - DMTT

Este é um sistema web que desenvolvi em Flask para gerenciar chamados de manutenção, controlar o estoque de itens e ferramentas, e administrar usuários e permissões em um ambiente de rede.

## Funcionalidades Principais

* **Portal de Solicitações:** Uma página pública para qualquer pessoa abrir um novo chamado de manutenção.
* **Acompanhamento Público:** Uma tela para consultar o status de chamados recentes sem a necessidade de login.
* **Gestão de Chamados:** Painel interno para a equipe de manutenção aprovar, rejeitar, comentar e finalizar chamados.
* **Controle de Estoque:** Cadastro e atualização de itens e ferramentas (consumíveis ou retornáveis).
* **Saída de Materiais:** Associação de itens do estoque a um chamado específico.
* **Controle de Acesso:** Sistema de permissões baseado em cargos (Admin, Manutenção, Gerenciador).
* **Histórico Completo:** Uma visão geral de todos os chamados já criados, incluindo os finalizados e excluídos.
* **Geração de PDF:** Emissão de relatórios de requisição de material em PDF.

### Funcionalidades de Administração e Supervisão

* **Trilha de Auditoria Completa:** Uma página de Supervisão, exclusiva para administradores, que registra todas as ações importantes no sistema: login, criação/atualização/exclusão de usuários e produtos, mudanças de status de chamados, etc.
* **Filtros Avançados:** A página de Supervisão permite filtrar os registros por usuário, tipo de ação e data.
* **Relatório de Movimentação de Estoque:** Geração de um relatório detalhado em PDF, mostrando para cada item a quantidade inicial, a quantidade atual, o percentual de uso e todo o histórico de movimentações.
* **Setup Automatizado:** Na primeira execução, a aplicação verifica se o banco de dados e as tabelas existem no servidor PostgreSQL e os cria automaticamente, facilitando a implantação.

## Tecnologias Utilizadas

* **Backend:** Python 3 com Flask
* **Banco de Dados:** PostgreSQL
* **ORM:** SQLAlchemy
* **Frontend:** HTML, CSS, JavaScript

---

## Configuração para Acesso em Rede (Cliente-Servidor)

Para que a aplicação (cliente) em um computador funcione com o banco de dados (servidor) em outro, siga estes dois passos.

### Passo 1: Na máquina SERVIDOR (onde o PostgreSQL está instalado)

O objetivo é permitir que o PostgreSQL aceite conexões de outros computadores na rede.

1.  **Edite o arquivo `postgresql.conf`:**
    * Procure pela linha `#listen_addresses = 'localhost'` e altere para:
    ```ini
    listen_addresses = '*'
    ```
    Isso faz o servidor "escutar" por conexões de qualquer endereço de rede, e não apenas da própria máquina.

2.  **Edite o arquivo `pg_hba.conf`:**
    * Adicione a seguinte linha ao final do arquivo:
    ```ini
    # Exemplo para uma rede 192.168.0.x
    host    all    all    192.168.0.0/24    md5

    # Exemplo para uma rede 10.124.129.x
    host    all    all    10.124.129.0/24   md5
    ```
    * **Explicação:** Esta linha autoriza qualquer usuário (`all`) de qualquer banco de dados (`all`) vindo de qualquer IP na faixa de rede especificada (`10.124.129.0/24`) a se conectar, desde que forneça uma senha válida (`md5`).
    * **IMPORTANTE:** O uso de `md5` é crucial para garantir a compatibilidade com a aplicação. O método mais moderno `scram-sha-256` pode talvez causar erros de `UnicodeDecodeError`. 
    * **DETALHE IMPORTANTE** Caso ainda esteja dando o problema de UnicodeDecodeError, provavelmente é melhor colocar tudo para scram-sha-256

3.  **Reinicie o serviço do PostgreSQL** para que as alterações tenham efeito.

### Passo 2: Na máquina CLIENTE (onde a aplicação `.exe` ou o código será executado)

1.  **Edite o arquivo `config.py`:**
2.  Atualize a `SQLALCHEMY_DATABASE_URI` com o endereço IP do **servidor** onde o banco de dados está.

    ```python
    # Exemplo:
    # 'postgresql://<usuario>:<senha>@<IP_DO_SERVIDOR>:<porta>/<nome_do_banco>'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:sua_senha_aqui@10.108.129.100:5432/controle_almox'
    ```

---

## Como Rodar (Ambiente de Desenvolvimento)

Siga estes passos se você é um desenvolvedor e deseja executar o código-fonte.

### 1. Pré-requisitos
* **Git:** Para clonar o repositório.
* **Python 3.10+**
* **PostgreSQL:** Instalado em uma máquina na rede (pode ser a sua localmente).

### 2. Preparar o Ambiente
1.  **Clonar o Repositório**
    ```bash
    git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
    cd seu-repositorio
    ```

2.  **Criar e Ativar o Ambiente Virtual**
    ```bash
    python -m venv venv
    # No Windows
    .\venv\Scripts\activate
    # No Linux/macOS
    source venv/bin/activate
    ```

3.  **Instalar as Dependências**
    ```bash
    pip install -r requirements.txt
    ```

### 3. Configurar e Executar
1.  Siga as instruções da seção **"Configuração para Acesso em Rede"** para configurar seu `postgresql.conf`, `pg_hba.conf` (se necessário) e o arquivo `config.py`.
2.  Execute o `app.py` para iniciar o servidor.
    ```bash
    python app.py
    ```
3.  Abra seu navegador e acesse o endereço que aparecer no terminal (ex: `http://127.0.0.1:8080`).

**Login Padrão (na primeira execução):**
* **Usuário:** `admin`
* **Senha:** `senha_interessante`

> **Importante:** Altere a senha do administrador imediatamente após o primeiro login!

---

## Compilando um Novo Executável (`.exe`)

Se você fez alterações no código e deseja gerar um novo arquivo `.exe` para distribuição.

1.  **Instalar o PyInstaller**
    ```bash
    pip install pyinstaller
    ```
2.  **Executar o Comando de Compilação (no Terminal)**
Se você fez alterações no código e deseja gerar um novo arquivo `.exe` para distribuição, use o comando abaixo. Ele foi atualizado para incluir a pasta `migrations` e o módulo `logging.config`, que são essenciais para o funcionamento correto do executável.

1.  **Garanta que o PyInstaller está instalado:** `pip install pyinstaller`.
2.  **Execute o Comando de Compilação (no Terminal):**
    ```bash
    pyinstaller --console --onefile --name="SistemaDeControle" --add-data="templates;templates" --add-data="static;static" --add-data="migrations;migrations" --add-binary="binarios_pdf;binarios_pdf" --hidden-import "logging.config" app.py
    ```
3.  **Encontrar o Arquivo:** O novo executável (`SistemaDeControle.exe`) estará na pasta `dist`.
