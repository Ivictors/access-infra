# Access Stack

Integração local dos repositórios [acess-gateway](https://github.com/Ivictors/acess-gateway), [access-web](https://github.com/Ivictors/access-web) e [device-simulator](https://github.com/Ivictors/device-simulator). O PostgreSQL pertence ao gateway; a web usa somente a API HTTP.

## Comunicação entre os projetos

```text
Navegador --HTTP/sessão PHP--> access-web --HTTP/Bearer administrativo--> acess-gateway --JDBC--> PostgreSQL
device-simulator -----------HTTP/Bearer do dispositivo-----------> acess-gateway
```

O navegador acessa somente a web PHP. A web consulta o gateway com o token administrativo configurado no servidor. O simulador envia eventos com a chave do dispositivo e usa o token administrativo apenas para consultar o histórico nos testes. O gateway autentica as chamadas, aplica as regras de acesso e é o único serviço que acessa seu banco. No Compose, web e gateway compartilham a rede `app`; gateway e PostgreSQL compartilham a rede interna `data`.

O laboratório [access-keycloak](https://github.com/Ivictors/access-keycloak) vive em um repositório próprio, com Compose e banco próprios. Ele ainda não participa dessas chamadas nem substitui o login atual.

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

Os critérios para uma futura implantação estão em [PRODUCTION.md](PRODUCTION.md).
