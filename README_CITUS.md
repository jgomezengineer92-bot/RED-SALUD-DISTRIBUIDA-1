# Historia Clínica Distribuida con PostgreSQL + Citus

Este laboratorio implementa una base de datos distribuida real usando PostgreSQL con la extensión **Citus**,
permitiendo fragmentar automáticamente los datos y distribuir las consultas de forma transparente.

---

## Arquitectura

- 1 Coordinator (puerto 5432)
- 2 Workers
- Todas las tablas distribuidas por `documento_id`, excepto `profesional_salud`, que es replicada.

---

## Requisitos

- Docker
- Docker Compose
- psql (cliente PostgreSQL)

---

## Instrucciones

1. Levanta los servicios:

```bash
docker compose -f docker-compose-citus.yml up -d
```

2. Espera ~15 segundos a que los contenedores arranquen, luego registra los workers:

```bash
docker exec -it citus_coordinator psql -U admin -d historia_clinica -c "CREATE EXTENSION IF NOT EXISTS citus;"
docker exec -it citus_coordinator psql -U admin -d historia_clinica -c "SELECT citus_set_coordinator_host('citus_coordinator', 5432);"
docker exec -it citus_coordinator psql -U admin -d historia_clinica -c "SELECT * FROM citus_add_node('citus_worker1', 5432);"
docker exec -it citus_coordinator psql -U admin -d historia_clinica -c "SELECT * FROM citus_add_node('citus_worker2', 5432);"
```

3. Verifica los workers registrados:

```bash
docker exec -it citus_coordinator psql -U admin -d historia_clinica -c "SELECT * FROM citus_get_active_worker_nodes();"
```

4. Ejecuta el esquema:

```bash
docker exec -i citus_coordinator psql -U admin -d historia_clinica < schema_citus.sql
```

5. Inserta datos de ejemplo:

```bash
docker exec -i citus_coordinator psql -U admin -d historia_clinica < insert_datos.sql
```

---

## Validación

Puedes hacer consultas distribuidas directamente desde el coordinador:

```sql
SELECT * FROM usuario WHERE documento_id > 0;
SELECT * FROM citus_shards;
SELECT * FROM citus_get_active_worker_nodes();
```

---

## Archivos

```
.
├── docker-compose-citus.yml
├── schema_citus.sql
├── insert_datos.sql
├── README_CITUS.md
```

---

## Autor

Laboratorio de Sistemas Distribuidos - MER
