# Netlists de exemplo do VIOLA

Os sete circuitos de exemplo distribuídos com o
[VIOLA](https://github.com/polimi-ispl/viola), mais um filtro RC e os netlists
usados na validação. Ficam aqui para que os testes e as ferramentas de
verificação rodem num clone deste repositório, sem precisar do framework MATLAB.

| Arquivo | Circuito | Classe |
|---|---|---|
| `rc_lowpass.txt` | filtro RC passa-baixas | `lin` |
| `DEMO.txt` | retificador de pico com diodo | `one_non_lin` |
| `SBGEQ.txt` | equalizador gráfico | `lin_opamp` |
| `MXR.txt` | MXR Distortion+ | `one_non_lin_opamp` |
| `MBB.txt` | Big Muff | `one_non_lin_opamp` |
| `MTG.txt` | Tone Gizmo | `one_non_lin_opamp` |
| `EHBMP.txt` | EH Bass Muff | `one_non_lin_opamp` |
| `DOD.txt` | DOD 250 | `non_lin_opamp` (SIM/DSR) |
| `TSCLIP.txt`, `screamo.txt` | estágios de clipping estilo Tube Screamer | `one_non_lin_opamp` |

Origem e licença: os arquivos `DEMO`, `DOD`, `EHBMP`, `MBB`, `MTG`, `MXR` e
`SBGEQ` vêm do repositório do VIOLA e são redistribuídos sob a GPL-3.0, com
crédito aos autores (ver `CREDITS.md` na raiz).
