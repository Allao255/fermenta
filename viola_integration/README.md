# Integração com o VIOLA (MATLAB)

Este repositório **não** redistribui o VIOLA (é um projeto de terceiros,
licenciado sob GPL-3.0, e traz binários grandes). Em vez disso, guardamos aqui
apenas os arquivos que **adicionamos** ao VIOLA para o nosso fluxo, e você os
copia para um clone limpo do VIOLA.

## Como usar

1. Clone o VIOLA oficial:

   ```bash
   git clone https://github.com/polimi-ispl/viola
   ```

2. Copie os arquivos desta pasta para dentro do clone:

   | Arquivo aqui | Vai para (no clone do VIOLA) |
   |---|---|
   | `main_TSCLIP.m` | `viola/windows/` |
   | `viola_export.m` | `viola/windows/` |
   | `viola_export_nl.m` | `viola/windows/` |
   | `viola_run_plugin.m` | `viola/windows/` |
   | `insertText.m` | `viola/windows/` (stub p/ evitar o Computer Vision Toolbox) |
   | `Netlist/TSCLIP.txt` | `viola/windows/Data/Input/Netlist/` |

3. Siga o `docs/GUIA_LTspice_para_VIOLA.md`.

## O que é cada arquivo

- `main_TSCLIP.m` — script principal pré-configurado que gera o nosso pedal de
  demonstração pelo VIOLA (netlist `TSCLIP`, saída `N005`, knobs Drive/Level).
- `viola_export.m` / `viola_export_nl.m` — rodam o pipeline numérico do VIOLA e
  exportam CSVs (sinais + matrizes Q, B, Z, S) para comparação com a nossa
  engine (lineares e não lineares).
- `viola_run_plugin.m` — instancia a classe de plugin gerada pelo VIOLA e roda
  `processBlock`, para comparar a saída do plugin de verdade.
- `insertText.m` — stub que dispensa o Computer Vision Toolbox num clone novo.
- `Netlist/TSCLIP.txt` — netlist de demonstração no formato do VIOLA (inclui os
  blocos `.subckt` dos componentes customizados).

> Crédito e licença do VIOLA: ver `CREDITS.md` na raiz.
