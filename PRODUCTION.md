# Preparação para produção

O manifesto `compose.release.yaml` reproduz uma combinação testada de imagens, mas vincula a web e a API a `127.0.0.1` e não configura uma entrada pública. Nenhum ambiente de produção está configurado neste repositório.

## Decisões necessárias

- Host ou provedor, domínio, política de DNS e responsável pelo certificado TLS.
- Forma de injetar e rotacionar `POSTGRES_PASSWORD`, `ACCESS_GATEWAY_ADMIN_TOKEN` e `ACCESS_WEB_PASSWORD_HASH` fora do Git. As aplicações atuais leem variáveis de ambiente; usar arquivos de segredo exige adaptar a inicialização.
- Política de retenção, destino externo e responsável pelos backups do PostgreSQL.
- Janela de manutenção e procedimento de reversão para migrações de banco incompatíveis.

## Critérios antes de expor a web

1. Colocar um proxy com TLS na frente da web e verificar a emissão/renovação do certificado. Manter a API e o PostgreSQL inacessíveis da rede pública. Ajustar e testar os cookies `Secure` da sessão PHP atrás do proxy.
2. Confirmar proteção contra tentativas repetidas de login e testar autenticação, encerramento de sessão e CSRF na configuração publicada.
3. Executar backup automatizado do PostgreSQL para armazenamento fora do host e **restaurar um backup em ambiente isolado**. Conferir que os eventos e dispositivos restaurados são consultáveis.
4. Promover somente digests que passaram pela CI de release. Registrar os digests em uso e observar saúde e logs após a troca.
5. Testar a reversão da web e do gateway com os digests anteriores. Para uma migração incompatível, usar o plano de banco definido antes da implantação; trocar a imagem não desfaz o esquema.

As decisões e a execução desses critérios estão acompanhadas na [issue #3](https://github.com/Ivictors/access-infra/issues/3). Até então, o Compose de release serve para validação local e não deve ser tratado como implantação pronta.
