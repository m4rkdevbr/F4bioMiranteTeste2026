-- =============================================================
-- Schema do banco legado de referencia
-- Dominio: nucleo bancario simplificado
-- =============================================================

CREATE TABLE clientes (
    id              BIGSERIAL PRIMARY KEY,
    nome            VARCHAR(200) NOT NULL,
    cpf             CHAR(11) NOT NULL UNIQUE,
    data_cadastro   TIMESTAMP NOT NULL DEFAULT NOW(),
    status          VARCHAR(20) NOT NULL DEFAULT 'ATIVO'
                    CHECK (status IN ('ATIVO','INATIVO','BLOQUEADO'))
);

CREATE TABLE contas (
    id              BIGSERIAL PRIMARY KEY,
    cliente_id      BIGINT NOT NULL REFERENCES clientes(id),
    agencia         VARCHAR(10) NOT NULL,
    numero          VARCHAR(20) NOT NULL,
    tipo            VARCHAR(20) NOT NULL
                    CHECK (tipo IN ('CORRENTE','POUPANCA','SALARIO')),
    saldo           NUMERIC(18,2) NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'ATIVA'
                    CHECK (status IN ('ATIVA','INATIVA','ENCERRADA')),
    data_abertura   TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (agencia, numero)
);

CREATE TABLE transacoes (
    id                  BIGSERIAL PRIMARY KEY,
    conta_origem_id     BIGINT REFERENCES contas(id),
    conta_destino_id    BIGINT REFERENCES contas(id),
    tipo                VARCHAR(20) NOT NULL
                        CHECK (tipo IN ('DEPOSITO','SAQUE','TRANSFERENCIA','TARIFA')),
    valor               NUMERIC(18,2) NOT NULL CHECK (valor > 0),
    data_transacao      TIMESTAMP NOT NULL DEFAULT NOW(),
    status              VARCHAR(20) NOT NULL DEFAULT 'EFETIVADA'
                        CHECK (status IN ('EFETIVADA','CANCELADA','ESTORNADA'))
);

CREATE TABLE taxas (
    id              BIGSERIAL PRIMARY KEY,
    tipo_operacao   VARCHAR(20) NOT NULL,
    percentual      NUMERIC(7,4) NOT NULL DEFAULT 0,
    valor_minimo    NUMERIC(18,2) NOT NULL DEFAULT 0,
    vigente_de      DATE NOT NULL,
    vigente_ate     DATE
);

CREATE TABLE log_auditoria (
    id              BIGSERIAL PRIMARY KEY,
    entidade        VARCHAR(50) NOT NULL,
    entidade_id     BIGINT,
    acao            VARCHAR(50) NOT NULL,
    detalhes        JSONB,
    criado_em       TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contas_cliente ON contas(cliente_id);
CREATE INDEX idx_transacoes_origem ON transacoes(conta_origem_id, data_transacao);
CREATE INDEX idx_transacoes_destino ON transacoes(conta_destino_id, data_transacao);
CREATE INDEX idx_log_entidade ON log_auditoria(entidade, entidade_id);
