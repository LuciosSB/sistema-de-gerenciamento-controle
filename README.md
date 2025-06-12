# Sistema de Gestão de Manutenção - DMTT

Este é um sistema web desenvolvido em Flask para gerenciar chamados de manutenção, controlar o estoque de itens e ferramentas, e administrar usuários e permissões.

## Funcionalidades Principais

* **Portal de Solicitações:** Uma página pública para qualquer pessoa abrir um novo chamado de manutenção.
* **Acompanhamento Público:** Uma tela para consultar o status de chamados recentes sem a necessidade de login.
* **Gestão de Chamados:** Painel interno para a equipe de manutenção aprovar, rejeitar, comentar e finalizar chamados.
* **Controle de Estoque:** Cadastro e atualização de itens e ferramentas (consumíveis ou retornáveis).
* **Saída de Materiais:** Associação de itens do estoque a um chamado específico.
* **Controle de Acesso:** Sistema de permissões baseado em cargos (Admin, Manutenção, Padrão).
* **Histórico Completo:** Uma visão geral de todos os chamados já criados, incluindo os finalizados e excluídos.
* **Geração de PDF:** Emissão de relatórios de requisição de material em PDF.

## Tecnologias Utilizadas

* **Backend:** Python 3 com Flask
* **Banco de Dados:** PostgreSQL
* **ORM:** SQLAlchemy
* **Frontend:** HTML, CSS, JavaScript
* **Templates:** Jinja2
* **Servidor WSGI (Produção):** Gunicorn

## Pré-requisitos do Servidor

Antes de instalar, garanta que o servidor (Linux ou Windows) tenha:

1.  **Python 3.10+**
2.  **PostgreSQL** instalado e um banco de dados criado para o projeto.
3.  **wkhtmltopdf:** Este é um programa externo necessário para gerar os PDFs.
    * No Linux (Debian/Ubuntu): `sudo apt-get install wkhtmltopdf`
    * No Windows: Baixar o instalador do [site oficial](https://wkhtmltopdf.org/downloads.html).

---

## Instalação e Configuração

Siga os passos abaixo para configurar o ambiente e rodar o projeto.

**1. Clonar o Repositório**
```bash
git clone <https://github.com/LuciosSB/sistema-de-gerenciamento-controle>
cd <controleAlmox-main - Copia>
```

**2. Criar e Ativar o Ambiente Virtual**
```bash
# Criar o ambiente
python -m venv venv

# Ativar no Windows
.\venv\Scripts\activate

# Ativar no Linux/macOS
source venv/bin/activate
```

**3. Instalar as Dependências**
```bash
pip install -r requirements.txt
```

**4. Configurar as Variáveis de Ambiente**

Crie um arquivo chamado `.env` na raiz do projeto. Ele guardará as informações sensíveis. Preencha com os dados do seu servidor:

```env
# Exemplo de arquivo .env
# Substitua com os seus próprios valores

# Chave secreta para a segurança da sessão do Flask
SECRET_KEY='mude-para-uma-frase-muito-longa-e-aleatoria'

# URL de conexão com o seu banco de dados PostgreSQL
DATABASE_URL='postgresql://<usuario>:<senha>@<host>:<porta>/<nome_do_banco>'

# Caminho para o executável do wkhtmltopdf no servidor
# Exemplo para Linux:
WKHTMLTOPDF_PATH='/usr/bin/wkhtmltopdf'
# Exemplo para Windows (se necessário):
# WKHTMLTOPDF_PATH='C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
```

**5. Criar as Tabelas no Banco de Dados**

Com o ambiente virtual ativado, execute o `app.py` uma vez para que ele crie as tabelas e o usuário `admin` inicial.

```bash
python app.py
```
Você verá a mensagem "Usuário 'admin' criado...". Você pode parar o servidor com `Ctrl+C` em seguida.

---

## Executando o Projeto

### Modo de Desenvolvimento

Para rodar em sua máquina local para testes e desenvolvimento:
```bash
flask --app app --debug run
```
Acesse `http://127.0.0.1:5000` no seu navegador.

### Modo de Produção (Servidor)

No servidor, use o **Gunicorn** para rodar a aplicação de forma mais robusta e performática.

```bash
gunicorn --bind 0.0.0.0:8000 app:app
```
* `--bind 0.0.0.0:8000`: Faz o servidor escutar em todas as interfaces de rede na porta 8000.
* `app:app`: Informa ao Gunicorn para procurar a instância da aplicação chamada `app` dentro do arquivo `app.py`.

A aplicação estará rodando no endereço do seu servidor, na porta 8000.

**Login Padrão:**
* **Usuário:** `admin`
* **Senha:** `admin123` (Lembre-se de alterar imediatamente após o primeiro login!)