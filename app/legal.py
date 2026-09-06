"""Página pública de política de privacidade.

Servida pelo próprio backend porque o Play Console exige uma URL pública
e o Cloud Run já tem HTTPS. Evita depender de outro serviço só para isso.
"""

# Preencha antes de publicar: vira o canal oficial de contato do app.
CONTACT_EMAIL = "ebagabe.2025@gmail.com"

LAST_UPDATED = "6 de setembro de 2026"

PRIVACY_HTML = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Política de Privacidade — Mnemio</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.65; max-width: 720px; margin: 0 auto; padding: 32px 20px 80px;
    color: #1D3357; background: #F6F4EF;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #F6F4EF; background: #1D3357; }}
    code {{ background: rgba(255,255,255,.1); }}
  }}
  h1 {{ font-size: 1.7rem; margin-bottom: 4px; }}
  h2 {{ font-size: 1.15rem; margin-top: 34px; }}
  .updated {{ opacity: .65; font-size: .9rem; margin-top: 0; }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 6px; }}
  code {{ background: rgba(0,0,0,.06); padding: 1px 5px; border-radius: 4px; font-size: .9em; }}
</style>
</head>
<body>
<h1>Política de Privacidade do Mnemio</h1>
<p class="updated">Última atualização: {LAST_UPDATED}</p>

<p>O Mnemio é um aplicativo para você registrar e acompanhar livros, séries,
filmes e animes. Esta política descreve exatamente quais dados o aplicativo
coleta, por que coleta e o que você pode fazer com eles.</p>

<h2>1. Dados que coletamos</h2>
<p>Coletamos apenas o que você digita no aplicativo:</p>
<ul>
  <li><strong>Nome e endereço de e-mail</strong>, informados no cadastro, usados
      para identificar sua conta e permitir o login.</li>
  <li><strong>Senha</strong>, armazenada exclusivamente como hash criptográfico
      (bcrypt). Não guardamos nem temos como recuperar sua senha original.</li>
  <li><strong>Conteúdo das suas coleções</strong>: títulos, notas de avaliação,
      status, progresso de leitura ou de episódios e as anotações que você
      escrever.</li>
</ul>
<p>O aplicativo <strong>não</strong> coleta localização, contatos, fotos,
identificadores de publicidade, nem dados de outros aplicativos. Não usamos
ferramentas de analytics nem exibimos anúncios.</p>

<h2>2. Como usamos os dados</h2>
<p>Os dados são usados unicamente para operar o aplicativo: autenticar você e
exibir suas próprias coleções, estatísticas e conquistas. Cada conta enxerga
somente os próprios dados.</p>
<p>Não vendemos, alugamos nem compartilhamos seus dados com terceiros para fins
comerciais ou publicitários.</p>

<h2>3. Onde os dados ficam</h2>
<p>Os dados ficam em um banco PostgreSQL gerenciado pela Neon e o aplicativo é
executado no Google Cloud Run. Dependendo da região configurada, esses
servidores podem estar localizados fora do Brasil. O tráfego entre o aplicativo
e o servidor é sempre criptografado por HTTPS.</p>

<h2>4. Exclusão da sua conta</h2>
<p>Você pode excluir sua conta a qualquer momento, direto no aplicativo, em
<strong>Perfil → Excluir conta</strong>.</p>
<p>A exclusão é imediata e permanente: apagamos seu cadastro, todas as suas
coleções, anotações e conquistas. A ação não pode ser desfeita e não mantemos
cópias.</p>
<p>Se preferir, envie um pedido para <code>{CONTACT_EMAIL}</code> a partir do
e-mail cadastrado, e faremos a exclusão manualmente.</p>

<h2>5. Seus direitos</h2>
<p>Conforme a Lei Geral de Proteção de Dados (LGPD), você pode solicitar acesso,
correção ou exclusão dos seus dados pessoais. Acesso e correção estão
disponíveis dentro do próprio aplicativo; a exclusão está descrita acima.</p>

<h2>6. Menores de idade</h2>
<p>O Mnemio não é direcionado a crianças e não coleta intencionalmente dados de
menores de 13 anos.</p>

<h2>7. Alterações nesta política</h2>
<p>Se esta política mudar, a data de atualização no topo da página será alterada.
Mudanças relevantes serão comunicadas no aplicativo.</p>

<h2>8. Contato</h2>
<p>Dúvidas sobre privacidade ou sobre seus dados: <code>{CONTACT_EMAIL}</code></p>
</body>
</html>
"""
