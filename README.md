# Sistema de Gestão de Manutenção - DMTT

Este é um sistema web desenvolvido em Flask para gerenciar chamados de manutenção, controlar o estoque de itens e ferramentas, e administrar usuários e permissões.

## Funcionalidades Principais

* **Portal de Solicitações:** Uma página pública para qualquer pessoa abrir um novo chamado de manutenção.
* **Acompanhamento Público:** Uma tela para consultar o status de chamados recentes sem a necessidade de login.
* **Gestão de Chamados:** Painel interno para a equipe de manutenção aprovar, rejeitar, comentar e finalizar chamados.
* **Controle de Estoque:** Cadastro e atualização de itens e ferramentas (consumíveis ou retornáveis).
* **Saída de Materiais:** Associação de itens do estoque a um chamado específico.
* **Controle de Acesso:** Sistema de permissões baseado em cargos (Admin, Manutenção, Gerenciador).
* **Histórico Completo:** Uma visão geral de todos os chamados já criados, incluindo os finalizados e excluídos.
* **Geração de PDF:** Emissão de relatórios de requisição de material em PDF.

## Tecnologias Utilizadas

* **Backend:** Python 3 com Flask
* **Banco de Dados:** PostgreSQL
* **ORM:** SQLAlchemy
* **Frontend:** HTML, CSS, JavaScript
* **Templates:** Jinja2

---

## Opção 1: Rodando a Versão Pronta (Executável)

Siga estes passos se você quer apenas usar o sistema em um computador Windows sem lidar com código-fonte.

### Passo 1: Pré-requisitos de Ambiente
Antes de rodar o programa, seu computador precisa ter dois softwares instalados. **O sistema não funcionará sem eles.**

1.  **PostgreSQL:** O sistema de banco de dados.
    * Baixe e instale a partir do [site oficial](https://www.postgresql.org/download/). Durante a instalação, defina uma senha para o usuário `postgres` e guarde-a.
2.  **wkhtmltopdf:** A ferramenta para gerar PDFs.
    * Baixe e instale a partir do [site oficial](https://wkhtmltopdf.org/downloads.html). Mantenha o caminho de instalação padrão (em `C:\Program Files\wkhtmltopdf`).

### Passo 2: Baixar e Configurar o Sistema
1.  Vá até a [página de Releases](https://github.com/LuciosSB/sistema-de-gerenciamento-controle/releases) deste repositório.
2.  Baixe o arquivo `app.exe` da versão mais recente.
3.  Crie uma pasta no seu computador (ex: `C:\SistemaDMTT`) e coloque o `app.exe` dentro dela.

### Passo 3: Executar e Usar
1.  Dê um duplo clique no arquivo `app.exe`.
2.  Uma janela de terminal preta irá aparecer. **Não feche esta janela**, pois ela é o servidor do sistema.
3.  Abra seu navegador de internet e acesse o endereço: `http://127.0.0.1:5000`
4.  Na primeira execução, o sistema criará o usuário administrador padrão.

**Login Padrão:**
* **Usuário:** `admin`
* **Senha:** `admin123`

> **Importante:** Altere a senha do administrador imediatamente após o primeiro login por questões de segurança!

---

## Opção 2: Ambiente de Desenvolvimento (Para Modificar o Código)

Siga estes passos se você é um desenvolvedor e deseja clonar o código-fonte para fazer alterações ou contribuir com o projeto.

### Passo 1: Pré-requisitos
* **Git:** Para clonar o repositório.
* **Python 3.10+**
* **PostgreSQL** e **wkhtmltopdf** (siga as mesmas instruções da "Opção 1").

### Passo 2: Preparar o Ambiente
1.  **Clonar o Repositório**
    ```bash
    git clone [https://github.com/LuciosSB/sistema-de-gerenciamento-controle.git](https://github.com/LuciosSB/sistema-de-gerenciamento-controle.git)
    cd sistema-de-gerenciamento-controle
    ```

2.  **Criar e Ativar o Ambiente Virtual**
    ```bash
    # Criar
    python -m venv venv

    # Ativar no Windows
    .\venv\Scripts\activate

    # Ativar no Linux/macOS
    source venv/bin/activate
    ```

3.  **Instalar as Dependências Python**
    ```bash
    pip install -r requirements.txt
    ```

### Passo 3: Configurar a Aplicação
1.  Abra o arquivo `config.py`.
2.  **SECRET_KEY**: Altere a chave secreta para uma frase longa e aleatória.
3.  **SQLALCHEMY_DATABASE_URI**: Atualize com os dados do seu banco de dados PostgreSQL.
    ```python
    # Exemplo: 'postgresql://<usuario>:<senha>@<host>:<porta>/<nome_do_banco>'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:sua_senha_aqui@localhost:5432/controle_almox'
    ```
4.  **WKHTMLTOPDF_PATH**: Verifique se o caminho para o executável está correto para o seu sistema.

### Passo 4: Executar o Projeto em Modo de Desenvolvimento
1.  **Criar o Banco e o Usuário Admin (primeira vez)**
    Com o ambiente virtual ativado, execute:
    ```bash
    python app.py
    ```
    O terminal mostrará a mensagem "Usuário 'admin' criado...". Pare o servidor com `Ctrl+C`.

2.  **Rodar o Servidor de Desenvolvimento**
    ```bash
    flask --app app --debug run
    ```
    Acesse `http://127.0.0.1:5000` no seu navegador. O modo debug recarregará o servidor automaticamente a cada alteração no código.

---

## Compilando um Novo Executável (Opcional)

Se você fez alterações no código e deseja gerar um novo arquivo `.exe`, siga estes passos no seu ambiente de desenvolvimento.

1.  **Instalar o PyInstaller**
    ```bash
    pip install pyinstaller
    ```
2.  **Executar o Comando de Compilação**
    Rode o comando apropriado para o seu sistema operacional no terminal, a partir da pasta raiz do projeto.

    * **No Windows:**
        ```bash
        pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" app.py
        ```
    * **No Linux/macOS:**
        ```bash
        pyinstaller --onefile --add-data "templates:templates" --add-data "static:static" app.py
        ```
3.  **Encontrar o Arquivo**
    O novo executável estará na pasta `dist` que será criada no seu projeto.