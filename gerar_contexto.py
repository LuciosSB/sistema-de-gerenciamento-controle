import os

IGNORE_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'binarios_pdf', 'build', 'dist', 'migrations'}
INCLUDE_EXTS = {'.py', '.html', '.css', '.js', '.txt', '.md'}
IGNORE_FILES = {'gerar_contexto.py', 'package-lock.json', 'yarn.lock'}

output_file = 'CONTEXTO_COMPLETO.txt'

with open(output_file, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            file_ext = os.path.splitext(file)[1]
            if file in IGNORE_FILES:
                continue

            if file_ext in INCLUDE_EXTS or file == 'Procfile':
                file_path = os.path.join(root, file)
                outfile.write(f"\n{'=' * 50}\n")
                outfile.write(f"CAMINHO: {file_path}\n")
                outfile.write(f"{'=' * 50}\n")
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"Erro ao ler arquivo: {e}")

print(f"Pronto! Arquivo '{output_file}' gerado. Arraste ele para o Gemini.")