# Access Stack

Integração local dos repositórios [acess-gateway](https://github.com/Ivictors/acess-gateway), [access-web](https://github.com/Ivictors/access-web) e [device-simulator](https://github.com/Ivictors/device-simulator). O PostgreSQL pertence ao gateway; a web usa somente a API HTTP.

## Checkouts locais

O `compose.yaml` usa, por padrão, o layout atual em `C:\workspace\acess-project`:

```text
acess-project/
  access-infra/
  backend/acess-gateway/
  frontend/
  simulator/device-simulator/
```

Se os checkouts estiverem em outro layout, defina `BACKEND_CONTEXT` e `WEB_CONTEXT` com caminhos relativos a este arquivo Compose. O simulador é executado sob demanda no host.

## Iniciar

1. Copie `.env.example` para `.env`. Gere valores aleatórios para `POSTGRES_PASSWORD` e `ACCESS_GATEWAY_ADMIN_TOKEN`; o token administrativo deve ter pelo menos 32 caracteres. Nunca versione `.env`.
2. Gere `ACCESS_WEB_PASSWORD_HASH` com `php tools/hash-password.php` no repositório `access-web` ou com o comando Docker documentado no README desse projeto. Use uma senha diferente do token administrativo. Coloque o hash entre aspas simples no `.env`, pois ele contém `$` que o Compose interpretaria como variável.
3. Execute `docker compose up --build -d` nesta pasta.
4. Acesse a web em `http://127.0.0.1:8000`. A API fica em `http://127.0.0.1:8080`, disponível apenas no host local para cadastro e testes.

Para verificar o fluxo completo, configure no processo `ACCESS_GATEWAY_ADMIN_TOKEN` e `ACCESS_WEB_TEST_PASSWORD` com os mesmos valores usados no ambiente local e execute `python scripts/check-stack.py`. O script cadastra um dispositivo com identificador único, executa o simulador e consulta o resultado também pela web. Ele **grava um dispositivo e um evento** no banco local; use apenas em um ambiente de teste. `SIMULATOR_PATH`, `GATEWAY_URL` e `WEB_URL` permitem ajustar os caminhos e endereços.

`docker compose down` para os contêineres e preserva os dados. A remoção do volume é uma operação separada e destrutiva.

## Limites atuais

Este Compose é para desenvolvimento local. Implantação de produção requer imagens versionadas, HTTPS, gestão de segredos, backup, restauração e procedimento de reversão. Essas tarefas estão registradas nas issues deste repositório.

Uma combinação de imagens por digest está em `releases/current.env`; consulte [RELEASE.md](RELEASE.md) para validá-la e promovê-la. O manifesto de release ainda vincula as portas apenas a `127.0.0.1` e não configura TLS público.
