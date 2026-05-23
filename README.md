# 🛡️ RED SALUD DISTRIBUIDA — Historia Clínica P2P

[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](docker-compose.yml)
[![FHIR](https://img.shields.io/badge/HL7-FHIR%20R4-orange)](https://hl7.org/fhir/R4/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Citus-336791?logo=postgresql)](https://www.citusdata.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Grafana-E6522C?logo=prometheus)](prometheus/)

> **Resolución 866 de 2021 · MinSalud Colombia**  
> Arquitectura distribuida P2P para gestión de Historias Clínicas Electrónicas con HAPI FHIR R4, Citus, CouchDB, OAuth2/JWT y observabilidad Prometheus + Grafana.

---

## 🏗️ Arquitectura del Sistema

```
                    ┌─────────────────────────────────────────────┐
                    │           RED P2P SALUD DISTRIBUIDA          │
                    │                                              │
  ┌──────────┐      │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
  │ Frontend │──────┼──│ Nodo 1   │  │ Nodo 2   │  │ Nodo 3   │  │
  │ React    │      │  │ Guajira  │  │ Amazonas │  │ Guainía  │  │
  │ :3000    │      │  │ API:5000 │  │ API:5001 │  │ API:5002 │  │
  └──────────┘      │  │ DB:5984  │  │ DB:5985  │  │ DB:5986  │  │
                    │  │HAPI:8080 │  │HAPI:8081 │  │HAPI:8082 │  │
  ┌──────────┐      │  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
  │Prometheus│      │       │              │              │        │
  │ :9090    │      │  ┌────┴──────────────┴──────────────┘        │
  └──────────┘      │  │   Citus Coordinator (PostgreSQL)          │
  ┌──────────┐      │  │   :5432 — 57 campos Res. 866/2021         │
  │ Grafana  │      │  └─────────────────────────────────          │
  │ :3001    │      │   etcd-0 (Service Discovery) :2379           │
  └──────────┘      └─────────────────────────────────────────────┘
```

**Nodos geográficos simulados:** La Guajira · Amazonas · Guainía · Nariño  
**Stack:** React · Flask · CouchDB · PostgreSQL/Citus · HAPI FHIR R4 · etcd · Prometheus · Grafana

---

## 🚀 Despliegue Rápido

### Pre-requisitos
- Docker Engine ≥ 24 y Docker Compose v2
- Node.js ≥ 18 (solo para el frontend en desarrollo)
- 8 GB RAM mínimo (HAPI FHIR usa ~512 MB por instancia)

### 1. Levantar toda la infraestructura

```bash
git clone https://github.com/jgomezengineer92-bot/RED-SALUD-DISTRIBUIDA.git
cd RED-SALUD-DISTRIBUIDA
docker compose up -d
```

### 2. Verificar que todo está corriendo

```bash
# Estado de todos los contenedores
docker compose ps

# Health de los nodos API
curl http://localhost:5000/_up   # Guajira
curl http://localhost:5001/_up   # Amazonas
curl http://localhost:5002/_up   # Guainía

# CapabilityStatement HAPI FHIR (esperar ~60s al arranque)
curl http://localhost:8080/fhir/metadata | python3 -m json.tool | head -20
curl http://localhost:8081/fhir/metadata | python3 -m json.tool | head -20
curl http://localhost:8082/fhir/metadata | python3 -m json.tool | head -20

# Estado completo de un nodo (CouchDB + Citus + HAPI)
curl http://localhost:5000/health/full | python3 -m json.tool
```

### 3. Iniciar el Frontend

```bash
cd frontend
npm install
npm start
# Abrir http://localhost:3000
```

### 4. Abrir Dashboards de Observabilidad

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| Frontend React | http://localhost:3000 | — |
| **Grafana** | http://localhost:3001 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| HAPI FHIR Guajira | http://localhost:8080/fhir | — |
| HAPI FHIR Amazonas | http://localhost:8081/fhir | — |
| HAPI FHIR Guainía | http://localhost:8082/fhir | — |
| CouchDB Guajira | http://localhost:5984/_utils | admin / admin |

---

## 🔐 Autenticación OAuth2 / SMART on FHIR

Los endpoints `/hapi/*` están protegidos por JWT. Para obtener un token:

```bash
# Obtener token
curl -X POST http://localhost:5000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type":"client_credentials","client_id":"mi-cliente","scope":"patient/*.read patient/*.write"}'

# Usar el token
curl -X GET http://localhost:5000/hapi/Patient \
  -H "Authorization: Bearer <TOKEN>"
```

---

## 📋 Recursos FHIR Soportados (Requisito 3.2)

| Recurso FHIR | POST | GET | Nodos |
|---|---|---|---|
| **Patient** | ✅ `/hapi/Patient` | ✅ | 3 |
| **Encounter** | ✅ `/hapi/Encounter` | ✅ | 3 |
| **Observation** | ✅ `/hapi/Observation` | ✅ | 3 |
| **Condition** | ✅ `/hapi/Condition` | ✅ | 3 |
| **MedicationRequest** | ✅ `/hapi/MedicationRequest` | ✅ | 3 |

> Los recursos FHIR se crean **automáticamente** en HAPI al completar cada sección del flujo clínico.

---

## 🏥 Módulos Clínicos (57 campos · Res. 866/2021)

| Módulo | Campos | Endpoint Citus | Recurso FHIR |
|--------|--------|---------------|--------------|
| **Admisión** | 1–15 | `POST /recepcion/ingreso` | Patient |
| **Triage** | 16–24 | `POST /atencion/triaje` | Encounter + Observation |
| **Medicamentos** | 25–35 | `POST /atencion/medicamentos` | MedicationRequest |
| **Diagnóstico** | 36–39 | `POST /atencion/diagnostico` | Condition |
| **Egreso** | 40–57 | `POST /egreso/salida` | — |

---

## 🔍 Búsqueda Federada P2P

```bash
# Buscar un paciente en todos los nodos
curl http://localhost:5000/recepcion/buscar/1001001001
curl http://localhost:5001/recepcion/buscar/1001001001
curl http://localhost:5002/recepcion/buscar/1001001001

# Historia Clínica Completa consolidada
curl http://localhost:5000/hc/completa/1001001001 | python3 -m json.tool

# Métricas del dashboard
curl http://localhost:5000/reportes/metricas | python3 -m json.tool
```

---

## ⚠️ Simulación de Fallos

### Bajar un nodo (desde el frontend)
Ir a **⚙️ Nodos P2P** → clic en "Apagar Nodo".  
Los nodos restantes continúan operando con datos actualizados.

### Simular caída de BD
```bash
# Detener CouchDB de Guajira
docker compose stop guajira_db

# Verificar que el sistema detecta la caída
curl http://localhost:5000/health/full

# Restaurar
docker compose start guajira_db
```

### Chaos Engineering (Kubernetes)
```bash
chmod +x chaos/chaos.sh
./chaos/chaos.sh
```

---

## 📊 Stack de Observabilidad

- **Prometheus** scraping cada 15s: APIs Flask, HAPI FHIR, CouchDB  
- **Grafana** dashboard pre-configurado con:
  - Uptime de los 3 nodos API y HAPI FHIR
  - Request rate por nodo
  - Latencia p95 de endpoints
  - Errores HTTP 4xx/5xx
  - Estado de CouchDB

---

## 📁 Colección Postman

Importar el archivo [`postman/RED_SALUD_FHIR.postman_collection.json`](postman/RED_SALUD_FHIR.postman_collection.json) en Postman.

Contiene 9 carpetas con 20+ requests:
1. OAuth2 Token
2. HAPI FHIR Metadata (3 nodos)
3. Patient CRUD
4. Encounter
5. Observation
6. Condition
7. MedicationRequest
8. HC Consolidada y Reportes
9. Búsqueda Federada P2P

---

## 🗄️ Base de Datos Distribuida

- **CouchDB** — Motor documental P2P (1 instancia por nodo geográfico)
- **PostgreSQL/Citus** — BD transaccional distribuida con los 57 campos de la Resolución 866/2021
- **etcd** — Service discovery (registro de endpoints de cada nodo)

### Esquema Citus (tablas distribuidas)
```sql
hcd.usuario          -- 15 campos (sección I)
hcd.atencion         -- 9 campos  (sección II)
hcd.tecnologia_salud -- 11 campos (sección III)
hcd.diagnostico      -- 4 campos  (sección IV)
hcd.egreso           -- 18 campos (sección V)
```

---

## 🔒 Seguridad ISO 27001

| Control | Implementación |
|---------|----------------|
| **Disponibilidad** (A.17) | 4 nodos P2P, sin punto único de falla |
| **Integridad** (A.12) | SHA-256 en cada expediente, dual-storage (CouchDB + Citus) |
| **Anti-DoS** | Token Bucket Rate Limiter (20 req/burst, 1 req/s) |
| **Autenticación** | OAuth2 + JWT con scopes SMART on FHIR |

---

## 📦 Estructura del Proyecto

```
RED-SALUD-DISTRIBUIDA/
├── docker-compose.yml          # Stack completo (4 nodos + HAPI + Prometheus + Grafana)
├── backend/
│   ├── main.py                 # API Flask: 57 campos + OAuth2 + FHIR proxy + reportes
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── App.js              # React: 5 módulos clínicos + Dashboard + HC consolidada
│       └── App.css
├── sql/
│   └── schema_citus_full.sql   # Schema PostgreSQL/Citus completo
├── prometheus/
│   └── prometheus.yml          # Configuración de scraping
├── grafana/
│   └── provisioning/           # Datasources + dashboards auto-configurados
├── postman/
│   └── RED_SALUD_FHIR.postman_collection.json
├── k8s/                        # Manifests Kubernetes
├── chaos/
│   └── chaos.sh                # Script chaos engineering
└── docs/
    ├── arquitectura.html
    └── mer.html
```

---

## 📚 Referencias

1. MinSalud Colombia. *Resolución 866 de 2021 - Historia Clínica Electrónica*. 2021.
2. HL7 International. *FHIR R4 Specification*. https://hl7.org/fhir/R4/
3. Citus Data. *Citus: Distributed PostgreSQL*. https://www.citusdata.com/
4. HAPI FHIR. *Open Source FHIR Server*. https://hapifhir.io/
5. Prometheus. *Monitoring System*. https://prometheus.io/
6. Apache CouchDB. *Distributed Document Database*. https://couchdb.apache.org/
7. SMART Health IT. *SMART on FHIR Authorization*. https://smarthealthit.org/
8. etcd. *Distributed Reliable Key-Value Store*. https://etcd.io/
