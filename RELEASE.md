# Promover uma combinação de imagens

`releases/current.env` registra os digests exatos de PostgreSQL, gateway e web. O arquivo contém somente referências públicas de imagens e os commits de origem; segredos ficam no `.env` local, ignorado pelo Git. A combinação atual passou pelo fluxo de cadastro, ingestão idempotente e consulta web autenticada em 2026-11-25.

O modo padrão do verificador exige cadastro, atribuição e revogação de `credentialRef`. A CI de release usa temporariamente `--legacy` para os digests atuais, que antecedem esse contrato. Depois de promover imagens compatíveis, retire `--legacy` do workflow e execute o modo padrão; o resultado de 2026-11-25 não valida os novos cenários.

O manifesto atual também antecede a integração OIDC. O workflow `OIDC integration` verifica os checkouts atuais com Keycloak, mas não valida os digests de `releases/current.env`. Para promover OIDC, publique primeiro as imagens atualizadas do gateway e da web, fixe seus novos digests e execute o fluxo OIDC sobre essa combinação antes de alterar o manifesto de release. O Keycloak mantém versão, banco e ciclo de vida próprios.

## Validar uma candidata

1. Espere a CI e a publicação de cada repositório terminarem. Obtenha o digest publicado pelo workflow ou com `docker buildx imagetools inspect <imagem>:<tag>`.
2. Atualize somente a linha da imagem desejada em `releases/current.env` e o commit de origem no comentário. Use `@sha256:`; não use `latest` nem apenas uma tag.
3. Execute `docker compose --env-file .env --env-file releases/current.env -f compose.release.yaml config --quiet`.
4. Em um banco de teste, execute `docker compose --env-file .env --env-file releases/current.env -f compose.release.yaml up -d` e `python scripts/check-stack.py --legacy` com `ACCESS_GATEWAY_ADMIN_TOKEN` e `ACCESS_WEB_TEST_PASSWORD` configurados enquanto os digests forem antigos. O script grava um dispositivo e um evento. Para imagens compatíveis com atribuição, execute sem `--legacy`. Pare os contêineres com `docker compose --env-file .env --env-file releases/current.env -f compose.release.yaml down`, preservando o volume.
5. Publique a alteração do manifesto em um commit `chore: promote ...` e confira a CI do `access-infra`. Esse commit identifica a combinação aprovada.

## Reverter

Recupere os digests do commit anterior de `releases/current.env` e valide a combinação antes de aplicá-la. Uma reversão de imagem **não reverte migrações do PostgreSQL**; confirme a compatibilidade do esquema e tenha um backup restaurável antes de promover uma versão com mudanças de banco. O Compose local não substitui um plano de produção.

Este manifesto serve para reproduzir e testar localmente a combinação de imagens. O histórico da meta de produção está na [issue #3](https://github.com/Ivictors/access-infra/issues/3); seus requisitos não foram concluídos.
