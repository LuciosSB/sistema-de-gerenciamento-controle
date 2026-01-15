# 📦 Sistema de Gerenciamento e Controle de Almoxarifado

Sistema web desenvolvido em **Python (Flask)** para gestão completa de almoxarifado, controle de estoque, fluxo de solicitações e histórico de movimentações.

O sistema permite que funcionários abram chamados para requisição de materiais e que administradores gerenciem o estoque, aprovem/recusem pedidos e visualizem relatórios gerenciais através de um dashboard interativo.

---

## 🚀 Funcionalidades Principais

* **Dashboard Gerencial:** Visão geral com indicadores de estoque baixo, chamados pendentes e gráficos de atividade.
* **Controle de Estoque:** Cadastro, edição e exclusão de produtos com níveis mínimos de alerta.
* **Mural de Solicitações:** Acompanhamento global de pedidos em tempo real (Visão Pública).
* **Gestão de Chamados:** Fluxo de aprovação (Pendente -> Aprovado -> Concluído/Recusado) com conferência de devolução de materiais.
* **Histórico Completo:** Auditoria de todas as ações (Login, Criação, Edição, Baixa de material).
* **Níveis de Acesso:**
    * *Admin:* Acesso total ao sistema.
    * *Gerente:* Gestão de aprovações.
    * *Comum:* Apenas visualização e abertura de chamados.

---

## 🛠️ Pré-requisitos (Softwares Obrigatórios)

Para o sistema funcionar, você precisa instalar os softwares abaixo na máquina (o `requirements.txt` não instala estes itens):

1.  **Python 3.10+:** [Baixar Python](https://www.python.org/downloads/)
    * ⚠️ **Importante:** Marque a opção **"Add Python to PATH"** no início da instalação.

2.  **PostgreSQL 14+:** [Baixar PostgreSQL](https://www.postgresql.org/download/)
    * Anote a senha que você criar para o usuário `postgres` (padrão sugerida: `suasenha`).

3.  **WKHTMLTOPDF (Gerador de Relatórios):** [Baixar wkhtmltopdf](https://wkhtmltopdf.org/downloads.html)
    * Baixe a versão para Windows (MinGW-w64).
    * Instale o programa.
    * **Crucial:** Após instalar, verifique se a pasta `bin` dele (ex: `C:\Program Files\wkhtmltopdf\bin`) foi adicionada às Variáveis de Ambiente (PATH) do Windows. Se não, adicione manualmente, ou o Python não conseguirá gerar os PDFs.

4.  **Git:** [Baixar Git](https://git-scm.com/downloads) (Para baixar o código).

---

### 🚨 Nota sobre Erros de Instalação (Visual C++)
Se ao rodar `pip install` der um erro gigante vermelho mencionando "Microsoft Visual C++ 14.0 or greater is required":
* Baixe o [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
* Na instalação, marque apenas a caixa **"Desenvolvimento para Desktop com C++"**.

---

## ⚙️ Instalação e Configuração

Siga os passos abaixo no terminal (CMD, PowerShell ou Terminal do Linux):

### 1. Clonar o Repositório
```bash
git clone [https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git](https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git)
cd sistema-de-gerenciamento-controle
2. Criar o Ambiente Virtual (.venv)
Isso isola as bibliotecas do projeto para não conflitar com outras coisas no PC.

Bash

# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
3. Instalar as Dependências
Bash

pip install -r requirements.txt
🗄️ Configuração do Banco de Dados
O sistema utiliza PostgreSQL. Você deve criar um banco de dados vazio antes de rodar o sistema.

Abra o pgAdmin (ou terminal do Postgres).

Crie um banco de dados chamado: controle_almox.

Configure a conexão no arquivo config.py (ou .env se estiver utilizando).

🔧 Ajustando a String de Conexão (Local vs Remoto)
No arquivo de configuração (config.py ou app.py), procure pela linha SQLALCHEMY_DATABASE_URI.

Cenário A: Banco na Mesma Máquina (Localhost)

Python

# Formato: postgresql://USUARIO:SENHA@localhost:5432/NOME_DO_BANCO
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:suasenha@localhost:5432/controle_almox'
Cenário B: Banco em Outra Máquina (Servidor) Se o sistema rodar no PC do funcionário, mas o banco estiver no Servidor (ex: IP 192.168.1.50):

Python

SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:suasenha@192.168.1.50:5432/controle_almox'
Nota: Certifique-se que o arquivo pg_hba.conf do servidor permite conexões externas.

🔐 Autenticação (SCRAM-SHA-256 vs MD5)
O PostgreSQL mais novo usa scram-sha-256 por padrão. O driver psycopg2 já suporta isso.

Se der erro de autenticação: Verifique se a senha está correta.

Caso extremo: Se houver incompatibilidade de driver legado, altere o password_encryption no postgresql.conf para md5 e redefina a senha do usuário. Mas, na maioria dos casos atuais, não é necessário alterar nada, o sistema suporta o padrão moderno.

🏗️ Inicializando o Banco (Migrações)
Com o banco criado e configurado, rode os comandos para criar as tabelas automaticamente:

Bash

# Inicializa a pasta de migrações (se não existir)
flask db init

# Gera o script de migração
flask db migrate -m "Inicialização do banco"

# Aplica as tabelas no banco de dados
flask db upgrade
▶️ Executando o Sistema
Com tudo configurado, inicie o servidor:

Bash

python app.py
O sistema estará acessível em:

Nesta máquina: http://127.0.0.1:8080

Na rede local: http://SEU_IP_NA_REDE:8080 (Ex: https://www.google.com/search?q=http://192.168.0.15:8080)

🔑 Acesso Inicial (Admin)
O sistema deve criar um usuário administrador padrão na primeira execução (verifique o código app.py na seção cria_usuario_admin).

Credenciais Padrão:

Usuário: admin

Senha: dmtt2026ti

Importante: Após o primeiro acesso, recomenda-se criar usuários individuais para cada membro da equipe na aba "Usuários".

🆘 Solução de Problemas Comuns
1. Erro: "Role 'postgres' does not exist"

Verifique se o usuário no SQLALCHEMY_DATABASE_URI é realmente postgres. Algumas instalações usam o nome do usuário do Windows.

2. Erro: "Visual C++ Build Tools required" ao instalar requirements

Algumas bibliotecas Python precisam de compiladores C++. Baixe o "Build Tools for Visual Studio" no site da Microsoft e instale a carga de trabalho "Desenvolvimento para Desktop com C++".

3. CSS não carrega (Página Branca/Sem estilo)

Tente limpar o cache do navegador com CTRL + F5.

Verifique se o arquivo static/css/main.css não contém tags HTML dentro dele.

4. Acesso negado pelo Firewall

Se outras máquinas não conseguirem acessar o sistema, adicione uma regra de entrada no Firewall do Windows para a porta 8080 (TCP).

Desenvolvido por André - 2026.

---