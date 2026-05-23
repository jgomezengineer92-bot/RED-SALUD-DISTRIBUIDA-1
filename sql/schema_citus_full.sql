-- =====================================================================
-- RED SALUD DISTRIBUIDA — Schema PostgreSQL / Citus
-- Resolución 866 de 2021 — MinSalud Colombia
-- 57 campos obligatorios distribuidos en 6 tablas normalizadas
-- Compatible con: PostgreSQL 14+  |  Citus 11+ (ver comentarios)
-- =====================================================================

-- Para usar con Citus (Docker): descomenta las líneas SELECT create_*
-- Para usar con PostgreSQL estándar (clase): déjalas comentadas

CREATE SCHEMA IF NOT EXISTS hcd;
SET search_path TO hcd, public;

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS citus;  -- Solo si usas Citus

-- =====================================================================
-- [0] CATÁLOGOS DE REFERENCIA (tablas de validación de dominio)
-- =====================================================================

-- ISO-3166: Códigos de país
DROP TABLE IF EXISTS hcd.catalogo_iso3166 CASCADE;
CREATE TABLE hcd.catalogo_iso3166 (
    code  VARCHAR(3)   PRIMARY KEY,
    name  VARCHAR(100) NOT NULL
);
INSERT INTO hcd.catalogo_iso3166 (code, name) VALUES
('CO','Colombia'),('US','Estados Unidos'),('BR','Brasil'),
('AR','Argentina'),('MX','México'),('CL','Chile'),
('PE','Perú'),('VE','Venezuela'),('EC','Ecuador'),
('PA','Panamá'),('ES','España'),('DE','Alemania');

-- UCUM: Unidades clínicas de medida
DROP TABLE IF EXISTS hcd.catalogo_ucum CASCADE;
CREATE TABLE hcd.catalogo_ucum (
    code        VARCHAR(20)  PRIMARY KEY,
    description VARCHAR(120) NOT NULL
);
INSERT INTO hcd.catalogo_ucum (code, description) VALUES
('mg','Miligramo'),('g','Gramo'),('mL','Mililitro'),('L','Litro'),
('IU','Unidad Internacional'),('h','Hora'),('d','Día'),
('kg','Kilogramo'),('mcg','Microgramo'),('tab','Tableta'),
('cap','Cápsula'),('amp','Ampolla'),('sup','Supositorio');

-- CIE-10: Diagnósticos (catálogo educativo Res. 866/2021)
DROP TABLE IF EXISTS hcd.catalogo_cie10 CASCADE;
CREATE TABLE hcd.catalogo_cie10 (
    codigo     VARCHAR(8)   PRIMARY KEY,
    descripcion VARCHAR(255) NOT NULL
);
INSERT INTO hcd.catalogo_cie10 (codigo, descripcion) VALUES
('J00',   'Rinofaringitis aguda (resfriado común)'),
('J18.9', 'Neumonía, no especificada'),
('I10',   'Hipertensión esencial (primaria)'),
('E11',   'Diabetes mellitus tipo 2'),
('E11.9', 'Diabetes mellitus tipo 2 sin complicaciones'),
('K29.7', 'Gastritis, no especificada'),
('M54.5', 'Dolor lumbar'),
('A09',   'Diarrea y gastroenteritis de presunto origen infeccioso'),
('J45',   'Asma'),
('K21',   'Enfermedad por reflujo gastroesofágico'),
('N39',   'Otros trastornos del tracto urinario'),
('O80',   'Parto único espontáneo'),
('S06',   'Traumatismo intracraneal'),
('B20',   'Enfermedad por VIH'),
('Z00',   'Examen general — sin quejas ni diagnóstico'),
('F32',   'Episodio depresivo'),
('G40',   'Epilepsia'),
('L40',   'Psoriasis'),
('R05',   'Tos'),
('R51',   'Cefalea');

-- SNOMED CT: Vías administración, alergias, procedimientos
DROP TABLE IF EXISTS hcd.catalogo_snomed CASCADE;
CREATE TABLE hcd.catalogo_snomed (
    concept_id VARCHAR(20)  PRIMARY KEY,
    term       VARCHAR(255) NOT NULL,
    category   VARCHAR(50)  NOT NULL
);
INSERT INTO hcd.catalogo_snomed (concept_id, term, category) VALUES
('26643006', 'Vía oral',              'route'),
('46713006', 'Vía intravenosa',       'route'),
('78421000', 'Vía intramuscular',     'route'),
('6064005',  'Vía subcutánea',        'route'),
('91936005', 'Alergia a penicilina',  'allergy'),
('372687004','Alergia a aspirina',    'allergy'),
('235595009','Administración de medicamento', 'procedure'),
('225317005','Soporte respiratorio',  'procedure');

-- =====================================================================
-- [1] PROFESIONAL DE SALUD — Tabla de referencia replicada
--     (no cuenta en los 57 campos obligatorios del paciente)
-- =====================================================================
DROP TABLE IF EXISTS hcd.profesional_salud CASCADE;
CREATE TABLE hcd.profesional_salud (
    id_personal_salud  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre             VARCHAR(255) NOT NULL,
    especialidad       VARCHAR(100) NOT NULL,
    registro_medico    VARCHAR(30)  UNIQUE NOT NULL,
    correo             VARCHAR(150)
);
-- SELECT create_reference_table('hcd.profesional_salud');  -- Solo Citus

INSERT INTO hcd.profesional_salud VALUES
(uuid_generate_v4(),'Dra. Andrea Borrero Ruiz',  'Medicina Interna',    'RM-2045-COL', 'a.borrero@redsalud.co'),
(uuid_generate_v4(),'Dr. Luis Enrique Pineda',   'Urgencias y Emergencias','RM-1872-COL','l.pineda@redsalud.co'),
(uuid_generate_v4(),'Enf. Camila Hoyos Salas',   'Enfermería Clínica',  'RE-3301-COL', 'c.hoyos@redsalud.co'),
(uuid_generate_v4(),'Dr. Hernán Díaz Ospina',    'Medicina General',    'RM-0994-COL', 'h.diaz@redsalud.co');

-- =====================================================================
-- SECCIÓN 1 — DATOS DEL USUARIO / PACIENTE
-- Campos #01 al #15  (Resolución 866/2021 — Artículo 5, Sección I)
-- =====================================================================
DROP TABLE IF EXISTS hcd.usuario CASCADE;
CREATE TABLE hcd.usuario (
    -- Identificación del paciente
    documento_id          BIGINT       PRIMARY KEY,                         -- Campo #01: Número de documento de identificación
    tipo_documento        VARCHAR(10)  NOT NULL DEFAULT 'CC'
                          CHECK (tipo_documento IN ('CC','TI','CE','PA','RC','MS','PE','AS')),  -- Campo #02: Tipo de documento (CC=Cédula, TI=Tarjeta Identidad, CE=Cédula Extranjería, PA=Pasaporte, RC=Reg. Civil, MS=Menor Sin Id, PE=Permiso Especial, AS=Adulto Sin Id)
    pais_nacionalidad     VARCHAR(3)   NOT NULL DEFAULT 'CO',               -- Campo #03: País de nacimiento / nacionalidad (ISO-3166)

    -- Datos personales
    nombre_completo       VARCHAR(255) NOT NULL,                            -- Campo #04: Nombre completo del usuario
    fecha_nacimiento      DATE         NOT NULL,                            -- Campo #05: Fecha de nacimiento
    edad                  SMALLINT     CHECK (edad >= 0 AND edad <= 150),   -- Campo #06: Edad en la unidad de medida indicada
    unidad_edad           VARCHAR(10)  DEFAULT 'Años'
                          CHECK (unidad_edad IN ('Años','Meses','Días')),   -- Campo #07: Unidad de medida de la edad

    -- Caracterización demográfica
    sexo                  VARCHAR(10)  NOT NULL
                          CHECK (sexo IN ('M','F','I')),                    -- Campo #08: Sexo biológico (M=Masculino, F=Femenino, I=Indeterminado)
    genero                VARCHAR(50),                                      -- Campo #09: Género autopercibido
    ocupacion             VARCHAR(100),                                     -- Campo #10: Ocupación (CIUO-88 Colombia)

    -- Datos especiales
    voluntad_anticipada   BOOLEAN      DEFAULT FALSE,                       -- Campo #11: Documento de voluntad anticipada (Ley 1733/2014)
    categoria_discapacidad VARCHAR(80),                                     -- Campo #12: Categoría de discapacidad (Física, Visual, Auditiva, Mental, etc.)

    -- Residencia y pertenencia étnica
    pais_residencia       VARCHAR(3)   DEFAULT 'CO',                       -- Campo #13: País de residencia actual (ISO-3166)
    municipio_residencia  VARCHAR(100),                                     -- Campo #14: Municipio de residencia (DIVIPOLA)
    etnia                 VARCHAR(80),                                      -- Campo #15: Pertenencia étnica / grupo poblacional (Indígena, Afro, Raizal, Palenquero, Mestizo, etc.)

    -- Metadatos de integridad
    hash_integridad       VARCHAR(64),                                      -- Hash de integridad (calculado en backend)
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_pais_nac  FOREIGN KEY (pais_nacionalidad)  REFERENCES hcd.catalogo_iso3166(code),
    CONSTRAINT fk_pais_res  FOREIGN KEY (pais_residencia)    REFERENCES hcd.catalogo_iso3166(code)
);
-- SELECT create_distributed_table('hcd.usuario', 'documento_id');  -- Solo Citus

COMMENT ON TABLE hcd.usuario IS 'Sección I — Datos del usuario/paciente. Resolución 866/2021 MinSalud Colombia. Campos #01-#15.';

-- =====================================================================
-- SECCIÓN 2 — DATOS DE LA ATENCIÓN
-- Campos #16 al #24  (9 campos)
-- =====================================================================
DROP TABLE IF EXISTS hcd.atencion CASCADE;
CREATE TABLE hcd.atencion (
    atencion_id           BIGSERIAL    NOT NULL,
    documento_id          BIGINT       NOT NULL,                            -- FK → usuario.documento_id

    -- Datos del prestador y fecha
    entidad_salud         VARCHAR(255) NOT NULL,                            -- Campo #16: Nombre de la entidad / IPS prestadora
    fecha_ingreso         TIMESTAMPTZ  NOT NULL DEFAULT now(),              -- Campo #17: Fecha y hora de ingreso a la atención

    -- Modalidad y entorno
    modalidad_entrega     VARCHAR(50)  NOT NULL DEFAULT 'Presencial'
                          CHECK (modalidad_entrega IN
                              ('Presencial','Telemedicina','Domiciliaria','Extramural')), -- Campo #18: Modalidad de entrega del servicio
    entorno_atencion      VARCHAR(60)  NOT NULL DEFAULT 'Consulta'
                          CHECK (entorno_atencion IN
                              ('Urgencias','Hospitalización','Consulta','UCI','Quirófano',
                               'Domicilio','Remisión')),                    -- Campo #19: Entorno de atención donde se brinda el servicio

    -- Ingreso y motivo
    via_ingreso           VARCHAR(60)  CHECK (via_ingreso IN
                              ('Espontáneo','Referencia','Contrarreferencia',
                               'Orden Judicial','Remisión')),              -- Campo #20: Vía de ingreso del usuario
    causa_atencion        TEXT,                                             -- Campo #21: Causa / motivo de la atención (texto libre)

    -- Triage (urgencias)
    fecha_triage          TIMESTAMPTZ,                                      -- Campo #22: Fecha y hora de valoración del triage
    clasificacion_triage  VARCHAR(5)   CHECK (clasificacion_triage IN
                              ('I','II','III','IV','V')),                   -- Campo #23: Clasificación del triage (Escala Manchester I-V)

    -- Grupo poblacional
    comunidad_etnica      VARCHAR(100),                                     -- Campo #24: Comunidad / grupo étnico especial al que pertenece

    -- Metadatos
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (atencion_id, documento_id),
    CONSTRAINT fk_atencion_usuario FOREIGN KEY (documento_id) REFERENCES hcd.usuario(documento_id)
);
-- SELECT create_distributed_table('hcd.atencion', 'documento_id');  -- Solo Citus

COMMENT ON TABLE hcd.atencion IS 'Sección II — Datos de la atención. Resolución 866/2021. Campos #16-#24.';

-- =====================================================================
-- SECCIÓN 3 — TECNOLOGÍA EN SALUD (MEDICAMENTOS Y PROCEDIMIENTOS)
-- Campos #25 al #35  (11 campos)
-- =====================================================================
DROP TABLE IF EXISTS hcd.tecnologia_salud CASCADE;
CREATE TABLE hcd.tecnologia_salud (
    tecnologia_id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    documento_id              BIGINT       NOT NULL,                        -- FK → usuario.documento_id
    atencion_id               BIGINT,                                       -- FK → atencion.atencion_id

    -- Descripción del medicamento / tecnología
    descripcion_medicamento   VARCHAR(255) NOT NULL,                        -- Campo #25: Nombre o descripción de la tecnología en salud (medicamento, dispositivo, procedimiento)
    dosis                     VARCHAR(50),                                  -- Campo #26: Dosis prescrita
    via_administracion        VARCHAR(60),                                  -- Campo #27: Vía de administración (oral, IV, IM, etc.) — SNOMED CT
    frecuencia                VARCHAR(50),                                  -- Campo #28: Frecuencia de administración (ej: cada 8 horas)
    dias_tratamiento          SMALLINT     CHECK (dias_tratamiento > 0),    -- Campo #29: Número de días de tratamiento
    unidades_aplicadas        SMALLINT     DEFAULT 0,                      -- Campo #30: Cantidad de unidades dispensadas / aplicadas

    -- Responsable
    id_personal_salud         UUID,                                         -- Campo #31: Identificación del profesional de salud responsable → profesional_salud

    -- Finalidad y diagnóstico
    finalidad_tecnologia      VARCHAR(100),                                 -- Campo #32: Finalidad de la tecnología (Tratamiento, Prevención, Diagnóstico, Rehabilitación)
    tipo_diagnostico_ingreso  VARCHAR(60)  CHECK (tipo_diagnostico_ingreso IN
                                  ('Confirmado','Presuntivo','En estudio')), -- Campo #33: Tipo de diagnóstico de ingreso
    diagnostico_ingreso       VARCHAR(10),                                  -- Campo #34: Código CIE-10 del diagnóstico de ingreso
    tipo_diagnostico_egreso   VARCHAR(60)  CHECK (tipo_diagnostico_egreso IN
                                  ('Confirmado','Presuntivo','En estudio')), -- Campo #35: Tipo de diagnóstico de egreso

    -- Metadatos
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_ts_usuario    FOREIGN KEY (documento_id)      REFERENCES hcd.usuario(documento_id),
    CONSTRAINT fk_ts_profesional FOREIGN KEY (id_personal_salud) REFERENCES hcd.profesional_salud(id_personal_salud),
    CONSTRAINT fk_ts_cie10      FOREIGN KEY (diagnostico_ingreso) REFERENCES hcd.catalogo_cie10(codigo)
);
-- SELECT create_distributed_table('hcd.tecnologia_salud', 'documento_id');  -- Solo Citus

COMMENT ON TABLE hcd.tecnologia_salud IS 'Sección III — Tecnología en salud. Resolución 866/2021. Campos #25-#35.';

-- =====================================================================
-- SECCIÓN 4 — DIAGNÓSTICO DE EGRESO
-- Campos #36 al #39  (4 campos)
-- =====================================================================
DROP TABLE IF EXISTS hcd.diagnostico CASCADE;
CREATE TABLE hcd.diagnostico (
    diagnostico_id        BIGSERIAL    NOT NULL,
    documento_id          BIGINT       NOT NULL,                            -- FK → usuario.documento_id
    atencion_id           BIGINT,                                           -- FK → atencion.atencion_id

    -- Diagnósticos CIE-10
    diagnostico_egreso    VARCHAR(10)  NOT NULL,                            -- Campo #36: Diagnóstico PRINCIPAL de egreso (CIE-10) — OBLIGATORIO
    diagnostico_rel1      VARCHAR(10),                                      -- Campo #37: Diagnóstico relacionado 1 (CIE-10)
    diagnostico_rel2      VARCHAR(10),                                      -- Campo #38: Diagnóstico relacionado 2 (CIE-10)
    diagnostico_rel3      VARCHAR(10),                                      -- Campo #39: Diagnóstico relacionado 3 (CIE-10)

    -- Metadatos
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (diagnostico_id, documento_id),
    CONSTRAINT fk_diag_usuario  FOREIGN KEY (documento_id)   REFERENCES hcd.usuario(documento_id),
    CONSTRAINT fk_diag_cie10    FOREIGN KEY (diagnostico_egreso) REFERENCES hcd.catalogo_cie10(codigo)
);
-- SELECT create_distributed_table('hcd.diagnostico', 'documento_id');  -- Solo Citus

COMMENT ON TABLE hcd.diagnostico IS 'Sección IV — Diagnóstico de egreso. Resolución 866/2021. Campos #36-#39.';

-- =====================================================================
-- SECCIÓN 5 — DATOS DE EGRESO
-- Campos #40 al #57  (18 campos)
-- =====================================================================
DROP TABLE IF EXISTS hcd.egreso CASCADE;
CREATE TABLE hcd.egreso (
    egreso_id              BIGSERIAL    NOT NULL,
    documento_id           BIGINT       NOT NULL,                           -- FK → usuario.documento_id
    atencion_id            BIGINT,                                          -- FK → atencion.atencion_id

    -- Condiciones de salida
    fecha_salida           TIMESTAMPTZ  NOT NULL DEFAULT now(),             -- Campo #40: Fecha y hora de egreso / salida
    condicion_salida       VARCHAR(30)  NOT NULL DEFAULT 'Vivo'
                           CHECK (condicion_salida IN ('Vivo','Muerto')),   -- Campo #41: Condición del usuario al egreso
    diagnostico_muerte     VARCHAR(10),                                     -- Campo #42: Diagnóstico CIE-10 de causa básica de muerte (si aplica)

    -- Prestador responsable
    codigo_prestador       VARCHAR(30)  NOT NULL,                           -- Campo #43: Código del prestador que realiza el egreso (REPS)

    -- Incapacidades y licencias
    tipo_incapacidad       VARCHAR(60)  CHECK (tipo_incapacidad IN
                               ('Temporal','Permanente Parcial',
                                'Permanente Total','Gran Invalidez',
                                'No aplica')),                              -- Campo #44: Tipo de incapacidad generada
    dias_incapacidad       SMALLINT     CHECK (dias_incapacidad >= 0),      -- Campo #45: Número de días de incapacidad laboral
    dias_lic_maternidad    SMALLINT     CHECK (dias_lic_maternidad >= 0),   -- Campo #46: Días de licencia de maternidad/paternidad

    -- Antecedentes clínicos relevantes
    alergias               TEXT,                                            -- Campo #47: Alergias conocidas del usuario
    antecedentes_familiares TEXT,                                           -- Campo #48: Antecedentes familiares de importancia clínica
    riesgos_ocupacionales  TEXT,                                            -- Campo #49: Factores de riesgo ocupacional identificados

    -- Responsable del egreso
    responsable_egreso     VARCHAR(255) NOT NULL,                           -- Campo #50: Nombre del profesional responsable del egreso

    -- Datos de contacto y residencia del usuario
    zona_residencia        VARCHAR(20)  NOT NULL DEFAULT 'Urbana'
                           CHECK (zona_residencia IN ('Urbana','Rural',
                               'Centro Poblado')),                          -- Campo #51: Zona de residencia (Urbana / Rural)
    direccion_residencia   VARCHAR(255) NOT NULL,                           -- Campo #52: Dirección de residencia del usuario
    telefono               VARCHAR(30),                                     -- Campo #53: Teléfono de contacto del usuario
    correo_electronico     VARCHAR(150),                                    -- Campo #54: Correo electrónico del usuario

    -- Datos del responsable / acudiente
    nombre_responsable     VARCHAR(255),                                    -- Campo #55: Nombre completo del responsable / acudiente
    parentesco_responsable VARCHAR(60),                                     -- Campo #56: Parentesco o relación del responsable con el usuario
    telefono_responsable   VARCHAR(30),                                     -- Campo #57: Teléfono del responsable / acudiente

    -- Metadatos
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (egreso_id, documento_id),
    CONSTRAINT fk_egreso_usuario FOREIGN KEY (documento_id)       REFERENCES hcd.usuario(documento_id),
    CONSTRAINT fk_egreso_muerte  FOREIGN KEY (diagnostico_muerte)  REFERENCES hcd.catalogo_cie10(codigo)
);
-- SELECT create_distributed_table('hcd.egreso', 'documento_id');  -- Solo Citus

COMMENT ON TABLE hcd.egreso IS 'Sección V — Datos de egreso. Resolución 866/2021. Campos #40-#57.';

-- =====================================================================
-- RESUMEN DE LOS 57 CAMPOS (Resolución 866 de 2021)
-- =====================================================================
-- SECCIÓN 1 — usuario:         campos  #01 - #15  (15 campos)
-- SECCIÓN 2 — atencion:        campos  #16 - #24  ( 9 campos)
-- SECCIÓN 3 — tecnologia_salud: campos #25 - #35  (11 campos)
-- SECCIÓN 4 — diagnostico:     campos  #36 - #39  ( 4 campos)
-- SECCIÓN 5 — egreso:          campos  #40 - #57  (18 campos)
--                                             TOTAL:  57 campos
-- =====================================================================

-- =====================================================================
-- DATOS DE PRUEBA — 3 pacientes completos
-- =====================================================================

-- PACIENTE 1: Adulto masculino con hipertensión — Nodo La Guajira
INSERT INTO hcd.usuario (documento_id, tipo_documento, pais_nacionalidad,
    nombre_completo, fecha_nacimiento, edad, unidad_edad, sexo, genero,
    ocupacion, voluntad_anticipada, categoria_discapacidad,
    pais_residencia, municipio_residencia, etnia)
VALUES (1001001001,'CC','CO','Carlos Andrés Arias Mendoza','1990-05-12',
        34,'Años','M','Masculino','Ingeniero de Sistemas',FALSE,NULL,
        'CO','Riohacha','Mestizo');

-- PACIENTE 2: Adulta femenina con diabetes — Nodo Amazonas
INSERT INTO hcd.usuario (documento_id, tipo_documento, pais_nacionalidad,
    nombre_completo, fecha_nacimiento, edad, unidad_edad, sexo, genero,
    ocupacion, voluntad_anticipada, categoria_discapacidad,
    pais_residencia, municipio_residencia, etnia)
VALUES (1002002002,'CC','CO','María Concepción López Torres','1975-11-30',
        49,'Años','F','Femenino','Docente',FALSE,'Física',
        'CO','Leticia','Mestizo');

-- PACIENTE 3: Menor de edad — Nodo Guainía
INSERT INTO hcd.usuario (documento_id, tipo_documento, pais_nacionalidad,
    nombre_completo, fecha_nacimiento, edad, unidad_edad, sexo, genero,
    ocupacion, voluntad_anticipada, categoria_discapacidad,
    pais_residencia, municipio_residencia, etnia)
VALUES (1003003003,'TI','CO','Santiago Muriel Ríos','2012-03-08',
        12,'Años','M','Masculino','Estudiante',FALSE,NULL,
        'CO','Inírida','Indígena Puinave');

-- Atenciones
INSERT INTO hcd.atencion (documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
    entorno_atencion, via_ingreso, causa_atencion, fecha_triage, clasificacion_triage, comunidad_etnica)
VALUES
(1001001001,'Hospital Nicolás de Barros — Riohacha',  now()-INTERVAL '2 days','Presencial','Urgencias',     'Espontáneo',   'Crisis hipertensiva y cefalea intensa',now()-INTERVAL '2 days','II', NULL),
(1002002002,'Hospital San Rafael de Leticia',          now()-INTERVAL '5 days','Presencial','Consulta',      'Espontáneo',   'Control glicémico y ajuste de insulina', NULL,NULL,'Comunidad Mestiza'),
(1003003003,'Centro de Salud Puerto Inírida',          now()-INTERVAL '1 day', 'Presencial','Urgencias',     'Referencia',   'Fiebre alta persistente 5 días y convulsión febril',now()-INTERVAL '1 day','III',NULL);

-- Tecnología en salud (medicamentos)
WITH prof AS (SELECT id_personal_salud FROM hcd.profesional_salud ORDER BY nombre LIMIT 1)
INSERT INTO hcd.tecnologia_salud (documento_id, descripcion_medicamento, dosis, via_administracion,
    frecuencia, dias_tratamiento, unidades_aplicadas, id_personal_salud,
    finalidad_tecnologia, tipo_diagnostico_ingreso, diagnostico_ingreso, tipo_diagnostico_egreso)
SELECT 1001001001,'Enalapril 20 mg tableta','20 mg','Vía oral','Cada 12 horas',
       30,60,id_personal_salud,'Tratamiento','Confirmado','I10','Confirmado'
FROM prof;

WITH prof AS (SELECT id_personal_salud FROM hcd.profesional_salud ORDER BY nombre OFFSET 1 LIMIT 1)
INSERT INTO hcd.tecnologia_salud (documento_id, descripcion_medicamento, dosis, via_administracion,
    frecuencia, dias_tratamiento, unidades_aplicadas, id_personal_salud,
    finalidad_tecnologia, tipo_diagnostico_ingreso, diagnostico_ingreso, tipo_diagnostico_egreso)
SELECT 1002002002,'Insulina glargina 100 UI/mL','20 UI','Vía subcutánea','Cada 24 horas',
       90,90,id_personal_salud,'Tratamiento','Confirmado','E11.9','Confirmado'
FROM prof;

WITH prof AS (SELECT id_personal_salud FROM hcd.profesional_salud ORDER BY nombre OFFSET 2 LIMIT 1)
INSERT INTO hcd.tecnologia_salud (documento_id, descripcion_medicamento, dosis, via_administracion,
    frecuencia, dias_tratamiento, unidades_aplicadas, id_personal_salud,
    finalidad_tecnologia, tipo_diagnostico_ingreso, diagnostico_ingreso, tipo_diagnostico_egreso)
SELECT 1003003003,'Acetaminofén 250 mg/5 mL suspensión','15 mg/kg','Vía oral','Cada 6 horas',
       5,4,id_personal_salud,'Tratamiento','Presuntivo','J00','Confirmado'
FROM prof;

-- Diagnósticos
INSERT INTO hcd.diagnostico (documento_id, diagnostico_egreso, diagnostico_rel1, diagnostico_rel2, diagnostico_rel3)
VALUES
(1001001001,'I10',    'R51',   NULL,    NULL),
(1002002002,'E11.9',  NULL,    NULL,    NULL),
(1003003003,'J00',    'R05',   NULL,    NULL);

-- Egresos
INSERT INTO hcd.egreso (documento_id, fecha_salida, condicion_salida, diagnostico_muerte,
    codigo_prestador, tipo_incapacidad, dias_incapacidad, dias_lic_maternidad,
    alergias, antecedentes_familiares, riesgos_ocupacionales, responsable_egreso,
    zona_residencia, direccion_residencia, telefono, correo_electronico,
    nombre_responsable, parentesco_responsable, telefono_responsable)
VALUES
(1001001001, now()-INTERVAL '1 day',  'Vivo',NULL,'IPS-001-GUJ','Temporal',2,0,
 'Ibuprofeno (urticaria)','Padre: HTA, Madre: DM2','Sedentarismo, estrés laboral',
 'Dra. Andrea Borrero Ruiz','Urbana','Calle 15 # 8-45 Riohacha','3001234567',
 'c.arias@correo.co','Luisa Mendoza','Madre','3007654321'),

(1002002002, now()-INTERVAL '4 days', 'Vivo',NULL,'IPS-002-AMA','No aplica',0,0,
 'Penicilina (anafilaxia)','Madre: DM, Hermano: HTA','Exposición solar prolongada',
 'Dr. Hernán Díaz Ospina','Urbana','Carrera 8 # 12-60 Leticia','3109876543',
 'm.lopez@correo.co',NULL,NULL,NULL),

(1003003003, now(),                   'Vivo',NULL,'IPS-003-GUA','No aplica',0,0,
 'Sin alergias conocidas','Abuela materna: epilepsia','Sin riesgos identificados',
 'Enf. Camila Hoyos Salas','Rural','Vereda El Remanso — Inírida','3154567890',
 NULL,'Pedro Muriel','Padre','3154567891');
