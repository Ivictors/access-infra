# Promover uma combinação de imagens

`releases/current.env` registra os digests exatos de PostgreSQL, gateway e web. O arquivo contém somente referências públicas de imagens e os commits de origem; segredos ficam no `.env` local, ignorado pelo Git. A combinação atual passou pelo fluxo de cadastro, ingestão idempotente e consulta web autenticada em 2026-11-25.

## Validar uma candidata

1. Espere a CI e a publicação de cada repositório terminarem. Obtenha o digest publicado pelo workflow ou com `docker buildx imagetools inspect <imagem>:<tag>`.
2. Atualize somente a linha da imagem desejada em `releases/current.env` e o commit de origem no comentário. Use `@sha256:`; não use `latest` nem apenas uma tag.
3. Execute `docker compose --env-file .env --env-file releases/current.env -f compose.release.yaml config --quiet`.
4. Em um banco de teste, execute `docker compose --env-file .env --env-file releases/current.env -f compose.release.yaml up -d` e `python scripts/check-stack.py` com `ACCESS_GATEWAY_ADMIN_TOKEN` e `ACCESS_WEB_TEST_PASSWORD` configurados. O script grava um dispositivo e um evento. Pare os contêineres com `docker compose --env-file .env --env-file releases/current.env -f compose.release.yaml down`, preservando o volume.
5. Publique a alteração do manifesto em um commit `chore: promote ...` e confira a CI do `access-infra`. Esse commit identifica a combinação aprovada.

## Reverter

Recupere os digests do commit anterior de `releases/current.env` e valide a combinação antes de aplicá-la. Uma reversão de imagem **não reverte migrações do PostgreSQL**; confirme a compatibilidade do esquema e tenha um backup restaurável antes de promover uma versão com mudanças de banco. O Compose local não substitui um plano de produção.

Até definir host, domínio, TLS, segredos e backups, este manifesto serve para reproduzir e testar a combinação de imagens. A implantação de produção está na [issue #3](https://github.com/Ivictors/access-infra/issues/3).
