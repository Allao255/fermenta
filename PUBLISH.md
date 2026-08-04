# Como publicar no GitHub

O repositório já está preparado localmente (git inicializado, `.gitignore`,
`README.md`, `CREDITS.md`). Falta só criar o repo remoto e dar push, **da sua
máquina** (usando a sua conta/credenciais).

## Opção A — com o GitHub CLI (`gh`)

Se você tem o `gh` instalado e autenticado (`gh auth login`):

```bash
cd C:\Users\Pichau\Documents\wdfviola   # pasta local (pode renomear p/ fermenta, opcional)

git add .
git commit -m "Primeira versão: port Python do VIOLA + codegen C++/JUCE + GUI"

# cria o repo na sua conta, já com a licença GPL-3.0, e dá push
gh repo create fermenta --public --source=. --remote=origin --push --license GPL-3.0
```

> Se o `gh` reclamar que o repo não fica vazio para aplicar a licença, crie sem
> `--license` e adicione o `LICENSE` depois (Opção B, passo da licença).

## Opção B — pelo site + git

1. No GitHub, **New repository** → nome `fermenta` → marque **Add a license:
   GNU General Public License v3.0** → Create. (Isso já cria o `LICENSE`.)
2. Na sua máquina:

   ```bash
   cd C:\Users\Pichau\Documents\wdfviola   # pasta local (opcional renomear p/ fermenta)

   git add .
   git commit -m "Primeira versão: port Python do VIOLA + codegen C++/JUCE + GUI"

   git branch -M main
   git remote add origin https://github.com/<SEU_USUARIO>/fermenta.git

   # como o repo remoto já tem um commit (o LICENSE), traga-o antes:
   git pull --rebase origin main
   git push -u origin main
   ```

## O que NÃO vai subir (por design)

Conferido pelo `.gitignore`:

- `viola/` — o clone do VIOLA (GPL-3.0, com binários). Não redistribuímos;
  ver `viola_integration/` e `CREDITS.md`.
- `build/`, `dist/`, `*.egg-info/`, `__pycache__/` — artefatos.
- `examples/**/build/` e projetos exportados — regeneráveis pela GUI.
- `*.vst3`, `*.exe`, `*.obj` — binários.

Confira antes de commitar:

```bash
git status              # veja o que será adicionado
git check-ignore -v viola/   # confirma que viola/ está ignorado
```

## Licença

Ver `CREDITS.md`. A recomendação é **GPL-3.0** (alinhada ao VIOLA). Não é
aconselhamento jurídico — a escolha final é sua.
