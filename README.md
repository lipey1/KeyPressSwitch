# KeyPress Switch

Utilitário para Windows que mantém uma tecla do teclado **pressionada** enquanto um modo estiver ativo. Um botão ou tecla de *switch* liga e desliga o comportamento — útil para automações simples, testes e jogos em modo janela.

**Criado por [Felipe Estrela](https://github.com/lipey1)**

---

## Funcionalidades

- **Switch configurável** — qualquer tecla do teclado ou botão do mouse (ex.: botão do meio)
- **Tecla a segurar** — tecla do teclado que fica em *hold* enquanto ativo
- **Overlay** — widget fixo no canto superior esquerdo mostrando `ATIVO` / `INATIVO` e a tecla
- **Bandeja do sistema** — minimiza para a setinha do Windows; ícone com bolinha verde (ativo) ou vermelha (inativo)
- **Config persistente** — salva automaticamente em `%APPDATA%\KeyPressSwitch\config.json`
- **Som ao ligar/desligar** — tons ascendentes (ativar) e descendentes (desativar), opcional
- **Instância única** — não permite abrir dois apps ao mesmo tempo
- **Executável portable** — build one-file com PyInstaller

---

## Requisitos

- **Windows 10/11** (cenário principal)
- Python 3.10+ (para rodar pelo código-fonte)

### Dependências

```bash
pip install -r requirements.txt
```

| Pacote   | Uso                          |
|----------|------------------------------|
| `pynput` | Captura e simulação de teclas |
| `pystray`| Ícone na bandeja do sistema  |
| `pillow` | Ícones e overlay             |

---

## Uso rápido

### Pelo código-fonte

```bash
python main.py
```

### Pelo executável

Após o build, abra:

```
dist\KeyPressSwitch.exe
```

### Configuração

1. **Definir switch** — clique no botão e pressione a tecla ou botão do mouse que vai ligar/desligar
2. **Definir tecla** — clique no botão e pressione a tecla que deve ficar segurada
3. Use o switch no dia a dia; o status aparece na janela, no overlay e na bandeja
4. **Minimizar para bandeja** — único jeito de ir para a setinha; some da barra de tarefas e continua rodando
5. **X** ou minimizar normal → janela na barra de tarefas (não vai para a bandeja)
6. Para encerrar de verdade: **X** (com janela aberta) ou bandeja → **Sair**

---

## Build do executável

```bash
pip install pyinstaller
python build.py
```

Gera `dist\KeyPressSwitch.exe` (one-file, sem console).

> Feche o app antes de rebuildar — o Windows bloqueia sobrescrever o `.exe` em uso.

---

## Onde a config é salva

```
%APPDATA%\KeyPressSwitch\config.json
```

Exemplo:

```json
{
  "version": 1,
  "switch": { "type": "mouse", "button": "middle" },
  "hold": { "kind": "char", "value": "/" },
  "show_overlay": true
}
```

O estado ativo/inativo **não** é salvo — ao reiniciar o app sempre começa inativo.

---

## Overlay sobre outros apps

O overlay usa `HWND_TOPMOST` no Windows e fica visível sobre janelas normais e apps maximizados.

| Cenário                         | Overlay visível?      |
|---------------------------------|-----------------------|
| Desktop / apps / maximizado     | Sim                   |
| Jogo **borderless** / sem bordas| Sim                   |
| Jogo **fullscreen exclusivo**   | Não (limite do Windows)|
| Resolução diferente do monitor  | Sim — canto do monitor físico |

Para jogos, prefira **Borderless Windowed** em vez de fullscreen exclusivo.

---

## Bandeja do sistema

- **Duplo clique** no ícone → reabre a janela
- **Clique direito** → Abrir / Sair
- Ícone com bolinha **verde** = ativo, **vermelha** = inativo

---

## Limitações importantes

- **Fullscreen exclusivo** (DirectX/Vulkan): overlay e alguns comportamentos não funcionam — o Windows entrega a tela inteira ao jogo
- **Anti-cheat** (EAC, BattlEye, Vanguard): simulação de teclas pode ser bloqueada ou banível — use por sua conta e risco
- **Apps como administrador**: se o jogo roda como admin, execute o KeyPress Switch também como admin (UIPI)
- **Linux / macOS**: código roda parcialmente, mas bandeja, overlay e captura global têm limitações (Wayland, permissões de acessibilidade, etc.)

---

## Estrutura do projeto

```
key-press/
├── main.py           # Aplicação principal
├── build.py          # Gera enter.ico e compila o .exe
├── requirements.txt
├── enter.png         # Ícone do app
├── README.md
└── dist/             # Executável (após build, não versionado)
```

---

## Testar o overlay

1. Marque **Mostrar overlay**
2. Maximize o Chrome ou Bloco de Notas — o widget deve permanecer no canto superior esquerdo
3. Acione o switch — texto do overlay deve mudar entre `ATIVO` (verde) e `INATIVO` (vermelho) junto com a janela principal
4. Em jogos, teste em modo **sem bordas**

---

## Licença

Projeto pessoal. Consulte o autor para uso comercial ou redistribuição.
