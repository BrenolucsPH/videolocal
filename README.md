# VideoLocal

Aplicativo local para Windows com interface gráfica simples para salvar vídeos do YouTube em MP4 ou WebM, ou extrair áudio em MP3.

## Como abrir

1. Instale o Python 3.11 ou superior pelo [site oficial](https://www.python.org/downloads/windows/) e habilite **Add Python to PATH** durante a instalação.
2. Para suporte completo ao YouTube, instale o runtime Deno pelo [site oficial](https://deno.com/) (ou Node.js/Bun). Feche e reabra o aplicativo depois de instalar.
3. Abra `iniciar.bat`. Na primeira execução, ele cria um ambiente Python isolado nesta pasta e instala `yt-dlp[default]` diretamente do PyPI.
4. Cole um link HTTPS do YouTube, escolha formato/qualidade e a pasta de destino.

A primeira configuração precisa de internet. O aplicativo usa os pacotes declarados neste projeto e não baixa instaladores EXE de sites aleatórios. O código está legível e não coleta nem envia dados pessoais para um servidor deste projeto. A transferência se conecta ao YouTube por meio do yt-dlp.

## FFmpeg e formatos

MP4 e WebM podem exigir FFmpeg para juntar vídeo e áudio em algumas qualidades. MP3 sempre requer FFmpeg. Na [página de releases do projeto yt-dlp](https://github.com/yt-dlp/FFmpeg-Builds/releases), baixe `ffmpeg-master-latest-win64-gpl.zip` (para Windows 64 bits), extraia o ZIP e, no aplicativo, clique **Localizar FFmpeg** para escolher `bin/ffmpeg.exe`. O aplicativo também detecta automaticamente `bin/ffmpeg.exe` dentro da pasta do projeto e guarda o caminho de forma relativa. Assim, a configuração acompanha a pasta se você movê-la. Não é necessário alterar o PATH do Windows.

## Uso autorizado

Use apenas conteúdo que você enviou, para o qual tenha autorização ou cujo download seja permitido pelo serviço e pela legislação aplicável. Os Termos do YouTube limitam o download aos casos autorizados pelo serviço, pelos titulares ou pela lei: [Termos do YouTube (Brasil)](https://br.youtube.com/t/terms). O aplicativo não usa cookies de conta, não tenta contornar DRM e não faz downloads de playlists.

## Limites e segurança

- É uma ferramenta local, sem login, sem anúncios e sem telemetria própria.
- `yt-dlp` é software de terceiros, instalado do PyPI dentro do ambiente `.venv` deste projeto; atualize-o regularmente. `yt-dlp[default]` inclui dependências Python e os componentes EJS; um runtime JavaScript (como Deno) continua necessário para suporte completo ao YouTube.
- Nenhum software pode ser declarado “livre de vírus” sem uma verificação independente. Este projeto não inclui binários executáveis de terceiros; para reduzir risco, confira o código, obtenha Python, Deno e FFmpeg de fontes oficiais e mantenha o antivírus ativo.
- A disponibilidade de formatos e resoluções depende do vídeo. A qualidade escolhida é um limite máximo.
- Downloads podem não funcionar para conteúdo privado, pago, protegido ou indisponível.

