# Access Stack

## Login integrado com Keycloak

O [plano de integração](KEYCLOAK_INTEGRATION_PLAN.md) registra a arquitetura, a ordem das mudanças e os limites desta etapa.

O modo OIDC é opcional e usa o [repositório access-keycloak](https://github.com/Ivictors/access-keycloak). Inicie o Keycloak primeiro. Depois, nesta pasta, execute `docker compose --env-file ../access-keycloak/.env --env-file .env -f compose.yaml -f compose.oidc.yaml up --build -d`. O arquivo de ambiente do Keycloak fornece o segredo do cliente `access-web`; o `.env` deste repositório continua fornecendo as credenciais do PostgreSQL do gateway. Acesse a web em `http://localhost:8000`, entre com o usuário `access-admin` e a senha `ACCESS_LAB_USER_PASSWORD` do `.env` do Keycloak. Para verificar o fluxo completo, carregue `ACCESS_LAB_USER_PASSWORD` e `ACCESS_WEB_OIDC_CLIENT_SECRET` no ambiente do processo e execute `python scripts/check-oidc.py`; ele grava um dispositivo, uma referência e um evento no banco local.

Neste modo, a web redireciona o navegador para o Keycloak, troca o código OIDC no canal interno e envia o token do usuário ao gateway. O gateway valida o token para rotas administrativas. Dispositivos continuam usando suas chaves individuais. O logout da web encerra a sessão PHP e a sessão SSO do Keycloak. O modo sem `compose.oidc.yaml` mantém o login anterior para compatibilidade durante a migração.

Integração local dos repositórios [acess-gateway](https://github.com/Ivictors/acess-gateway), [access-web](https://github.com/Ivictors/access-web) e [device-simulator](https://github.com/Ivictors/device-simulator). O PostgreSQL pertence ao gateway; a web usa somente a API HTTP.

## Comunicação entre os projetos

```text
Navegador --HTTP/sessão PHP--> access-web --HTTP/Bearer administrativo--> acess-gateway --JDBC--> PostgreSQL
device-simulator -----------HTTP/Bearer do dispositivo-----------> acess-gateway
```

O navegador acessa a web PHP. No modo original, a web consulta o gateway com o token administrativo configurado no servidor. No modo OIDC, o navegador também visita o Keycloak para fazer login e a web repassa o token de acesso do usuário ao gateway. O simulador envia eventos com a chave do dispositivo e usa o token administrativo apenas para consultar o histórico nos testes do modo original. O gateway autentica as chamadas, aplica as regras de acesso e é o único serviço que acessa seu banco. No Compose, web e gateway compartilham a rede `app`; gateway e PostgreSQL compartilham a rede interna `data`.

O laboratório [access-keycloak](https://github.com/Ivictors/access-keycloak) vive em um repositório próprio, com Compose e banco próprios. A rede externa `access-keycloak_identity_app` conecta web e gateway ao Keycloak somente quando o arquivo `compose.oidc.yaml` é aplicado.

## Checkouts locais

O `compose.yaml` usa, por padrão, o layout atual em `C:\workspace\acess-project`:

```text
acess-project/
  access-infra/
  backend/acess-gateway/
  frontend/
  simulator/device-simulator/
  access-keycloak/                 # laboratório opcional e independente
```

Se os checkouts estiverem em outro layout, defina `BACKEND_CONTEXT` e `WEB_CONTEXT` com caminhos relativos a este arquivo Compose. O simulador é executado sob demanda no host.

## Iniciar

1. Copie `.env.example` para `.env`. Gere valores aleatórios para `POSTGRES_PASSWORD` e `ACCESS_GATEWAY_ADMIN_TOKEN`; o token administrativo deve ter pelo menos 32 caracteres. Nunca versione `.env`.
2. Gere `ACCESS_WEB_PASSWORD_HASH` com `php tools/hash-password.php` no repositório `access-web` ou com o comando Docker documentado no README desse projeto. Use uma senha diferente do token administrativo. Coloque o hash entre aspas simples no `.env`, pois ele contém `$` que o Compose interpretaria como variável.
3. Execute `docker compose up --build -d` nesta pasta.
4. Acesse a web em `http://127.0.0.1:8000`. A API fica em `http://127.0.0.1:8080`, disponível apenas no host local para cadastro e testes.

Para verificar o fluxo completo, configure no processo `ACCESS_GATEWAY_ADMIN_TOKEN` e `ACCESS_WEB_TEST_PASSWORD` com os mesmos valores usados no ambiente local e execute `python scripts/check-stack.py`. O script cadastra um dispositivo e duas referências de credencial, atribui uma delas ao dispositivo, verifica rejeição de eventos inválidos e não atribuídos, executa o simulador com reenvio idempotente, revoga a atribuição e testa consulta, CSRF e logout na web. Ele **grava um dispositivo, duas referências e dois eventos** no banco local; use apenas em um ambiente de teste isolado. `SIMULATOR_PATH`, `GATEWAY_URL` e `WEB_URL` permitem ajustar os caminhos e endereços.

O modo `python scripts/check-stack.py --legacy` existe temporariamente para validar os digests antigos em `releases/current.env`, que ainda não implementam cadastro e atribuição de referências. Ele cadastra um dispositivo e grava um evento, além de testar CSRF e logout. Use o modo padrão para os checkouts atuais.

`docker compose down` para os contêineres e preserva os dados. A remoção do volume é uma operação separada e destrutiva.

## Limites atuais

Este projeto é usado para estudo e testes locais; não há implantação de produção planejada. Uma implantação real exigiria HTTPS, gestão de segredos, backup, restauração e procedimento de reversão. O encerramento das issues de produção registra uma mudança de objetivo, não o cumprimento desses requisitos.

Uma combinação de imagens por digest está em `releases/current.env`; consulte [RELEASE.md](RELEASE.md) para validá-la e promovê-la. O manifesto de release ainda vincula as portas apenas a `127.0.0.1` e não configura TLS público.

`releases/current.env` ainda aponta para imagens anteriores ao OIDC. O modo OIDC foi validado com imagens construídas dos checkouts locais e por seu workflow de integração; a combinação imutável de release só deve ser atualizada após a publicação dos novos digests e a execução do teste OIDC com essas imagens.

Os critérios para uma futura implantação estão em [PRODUCTION.md](PRODUCTION.md).
## Padrão de configuração local

Este repositório existe para integrar e validar o ambiente do Access Gateway.
Sua arquitetura e seus componentes estão descritos nas seções anteriores e
seguem o princípio de separar integração, execução e verificação da stack.

### Clonar e configurar

```powershell
git clone https://github.com/Ivictors/access-infra.git
cd access-infra
Copy-Item .env.example .env
```

Preencha o `.env` somente com valores locais. Nunca publique senhas, tokens,
hashes ou chaves no README, no histórico Git ou em imagens de contêiner.
