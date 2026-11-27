# Plano de integração do Keycloak

## Objetivo e limite

Centralizar a autenticação de pessoas no Keycloak para a web PHP e as operações administrativas do gateway. As chaves individuais dos dispositivos continuam no gateway. Kafka e ferramentas de observabilidade ficam fora desta etapa. A integração é opcional para preservar os testes e a migração gradual do modo anterior.

## Lugar do Keycloak

`access-keycloak` é um repositório independente, com Compose, realm e PostgreSQL próprios. No ambiente local, publica `http://localhost:8180` para o navegador e a rede Docker `access-keycloak_identity_app` para web e gateway. `access-infra` apenas conecta os serviços a essa rede por meio de `compose.oidc.yaml`; nenhum outro repositório precisa incorporar o banco ou o ciclo de vida do Keycloak.

## Comunicação no modo OIDC

```text
Navegador -> web PHP -> Keycloak: redirecionamento e troca do código de autorização
web PHP -> gateway: HTTP com token de acesso do usuário
gateway -> Keycloak: consulta das chaves públicas para validar o JWT
dispositivo -> gateway: HTTP com chave individual do dispositivo
gateway -> PostgreSQL: JDBC, dados dos dispositivos e eventos
```

O gateway valida assinatura, expiração, emissor, audiência `access-gateway` e papel `access-admin` antes de autorizar operações administrativas. O token administrativo compartilhado não é aceito no modo OIDC. A web guarda os tokens na sessão PHP, consulta o usuário no Keycloak e renova o token de acesso quando necessário. O logout atual encerra a sessão PHP local.

## Etapas de implementação

1. Preparar realm, cliente confidencial, usuário de demonstração e rede externa em `access-keycloak`.
2. Adicionar validação de JWT administrativo ao gateway, mantendo a chave do dispositivo no fluxo existente.
3. Adicionar Authorization Code à web e usar o token do usuário nas chamadas ao gateway.
4. Criar a sobreposição `compose.oidc.yaml` e documentar a ordem de inicialização.
5. Validar Compose, login, autorização, evento do dispositivo e consulta pela web. Executar também as suítes legadas.

## Uso local

Inicie `access-keycloak` antes da stack. Em `access-infra`, use `docker compose --env-file ../access-keycloak/.env --env-file .env -f compose.yaml -f compose.oidc.yaml up --build -d`. O `.env` de cada repositório é local e ignorado pelo Git. O importador do Keycloak só cria o realm na primeira inicialização; alterações posteriores no JSON exigem atualização do realm já existente.

## Limites desta etapa

O Compose usa `start-dev` e endereços `localhost`, próprios do laboratório local. O encerramento global da sessão SSO do Keycloak e a remoção do modo administrativo antigo são decisões de uma etapa posterior.
