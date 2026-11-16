# VideoLocal

Aplicativo para Windows que baixa vídeos e áudios do **YouTube**, **X (Twitter)** e **Instagram** direto para o seu computador, com fila de downloads, miniaturas e tema claro/escuro.

## Como usar

1. Abra `dist\VideoLocal\VideoLocal.exe` (veja abaixo como gerar). Não é preciso ter Python instalado para usar o executável.
2. Cole o link do vídeo. O aplicativo reconhece a plataforma automaticamente.
3. Escolha **Vídeo** (MP4 ou WEBM, até 4K) ou **Áudio** (MP3 ou M4A) e a qualidade.
4. Clique em **Baixar**. Você pode enfileirar vários links; eles são baixados um por vez.

Ao terminar, cada item oferece atalhos para reproduzir o arquivo, abrir a pasta ou removê-lo da lista. As preferências (pasta, formato, tema) ficam em `%APPDATA%\VideoLocal\settings.json`.

A pasta `dist\VideoLocal` é independente: pode ser movida ou copiada para outro computador, desde que o `VideoLocal.exe` continue junto das pastas `_internal` e `bin`.

## Gerar o executável

Requer Python 3.11 ou superior. No PowerShell, dentro da pasta do projeto:

```powershell
.\build.ps1
```

O script cria o ambiente `.venv`, instala as dependências, empacota o aplicativo com PyInstaller e copia `bin\ffmpeg.exe` e `bin\ffprobe.exe` para junto do executável. Se o PowerShell bloquear a execução do script, use `powershell -ExecutionPolicy Bypass -File .\build.ps1`.

## Requisitos opcionais

- **FFmpeg** — necessário para áudio (MP3/M4A) e para juntar vídeo e áudio nas melhores qualidades. O aplicativo procura `bin\ffmpeg.exe` ao lado do executável e depois no PATH; também é possível apontar o arquivo em **Configurações**. Baixe `ffmpeg-master-latest-win64-gpl.zip` na [página de releases do projeto yt-dlp](https://github.com/yt-dlp/FFmpeg-Builds/releases) e extraia `ffmpeg.exe` e `ffprobe.exe` para a pasta `bin`.
- **Runtime JavaScript** — o YouTube exige [Node.js](https://nodejs.org/) ou [Deno](https://deno.com/) instalado para funcionar por completo. X e Instagram não precisam.

## Conteúdo que exige login

Publicações privadas, restritas por idade ou bloqueadas por limite de acessos (comum no Instagram e no X) pedem uma sessão conectada. Em **Configurações → Sessão do navegador**, escolha o navegador em que você já está logado. O aplicativo lê os cookies desse navegador somente no momento do download e não os guarda. O Firefox é o mais confiável; Chrome e Edge costumam bloquear essa leitura no Windows.

Por padrão a opção fica em **Nenhum** e nenhum cookie é lido.

## Desenvolvimento

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py                         # abre o aplicativo
.venv\Scripts\python -m unittest discover -s tests  # testes
```

| Caminho | Função |
| --- | --- |
| `app.py` | Ponto de entrada |
| `videolocal/platforms.py` | Reconhece e valida os links de cada plataforma |
| `videolocal/downloader.py` | Converte as escolhas em opções do yt-dlp e executa o download |
| `videolocal/settings.py` | Preferências e caminhos (executável ou código-fonte) |
| `videolocal/ui.py` | Interface (CustomTkinter) |
| `tools/make_icon.py` | Gera os ícones em `assets/` |
| `build.ps1` | Gera o executável |

## Uso autorizado

Use apenas conteúdo que você enviou, para o qual tenha autorização ou cujo download seja permitido pelo serviço e pela legislação aplicável. Os termos do YouTube, do X e do Instagram limitam o download aos casos autorizados pelo serviço, pelos titulares ou pela lei. O aplicativo não contorna DRM e não baixa playlists inteiras.

## Limites e segurança

- Ferramenta local, sem conta própria, sem anúncios e sem telemetria. As conexões são feitas somente com a plataforma do link, por meio do yt-dlp.
- As plataformas mudam com frequência. Se os downloads pararem de funcionar, atualize o yt-dlp (`pip install -U "yt-dlp[default]"`) e gere o executável de novo.
- O executável não é assinado digitalmente; o Windows SmartScreen pode exibir um aviso na primeira abertura.
- A qualidade escolhida é um limite máximo: a disponibilidade depende de cada vídeo.
- Publicações apenas com fotos não são baixadas.
