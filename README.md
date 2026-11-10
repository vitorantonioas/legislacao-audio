# Legislação em Áudio

Feed: https://vitorantonioas.github.io/legislacao-audio/feed.xml

## Adicionar uma lei

```bash
python3 -m venv .venv && .venv/bin/pip install edge-tts beautifulsoup4
.venv/bin/python gerar_audios.py URL_DO_PLANALTO --sigla LRP --nome "Lei 6.015, de 1973, Lei de Registros Públicos"
python3 gerar_feed.py
git add audios feed.xml && git commit -m "Adiciona LRP" && git push
```

- Um MP3 por capítulo (Títulos sem capítulos viram um episódio). A numeração continua do último arquivo em `audios/`.
- `--so-texto` gera só os roteiros em `textos/` para revisar antes do áudio.
- `--voz pt-BR-FranciscaNeural` troca a voz; `--velocidade +15%` acelera.
- Se o Planalto recusar a conexão, salve a página no navegador e passe o arquivo `.htm` no lugar da URL.
