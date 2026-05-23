#!/bin/bash
set -e

cd /home/jesus/RED-SALUD-DISTRIBUIDA-1

echo "=== Fase 6: Tolerancia a Fallos ===" > fase6.txt

echo "--- Subfase A: Baseline ---" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT nodename, nodeport, isactive FROM pg_dist_node ORDER BY nodeid;" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT shardid, nodename, shardstate FROM pg_dist_shard_placement LIMIT 10;" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT COUNT(*) AS total_pacientes FROM usuario;" >> fase6.txt

echo "--- Subfase B: Detener worker1 ---" >> fase6.txt
docker stop citus_worker1
sleep 3
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT documento_id, nombre_completo FROM usuario ORDER BY documento_id;" >> fase6.txt 2>&1 || true

echo "--- Subfase C: Diagnóstico ---" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "
SELECT s.table_name AS tabla,
       p.shardid,
       p.nodename AS nodo_caido,
       p.shardstate,
       CASE p.shardstate
         WHEN 1 THEN 'ACTIVO'
         WHEN 3 THEN 'INACTIVO/ROTO'
         ELSE 'DESCONOCIDO'
       END AS estado
FROM pg_dist_shard_placement p
JOIN citus_shards s USING (shardid)
WHERE p.nodename LIKE '%worker1%'
ORDER BY s.table_name, p.shardid;" >> fase6.txt 2>&1 || true

echo "--- Subfase D: Consultas con nodo caído ---" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT COUNT(*) FROM usuario;" >> fase6.txt 2>&1 || true
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT * FROM profesional_salud;" >> fase6.txt 2>&1 || true
docker exec -i citus_worker2 psql -U admin -d historia_clinica -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' LIMIT 2;" >> fase6.txt 2>&1 || true

echo "--- Subfase E: Recuperar nodo ---" >> fase6.txt
docker start citus_worker1
sleep 8
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT citus_activate_node('citus_worker1', 5432);" >> fase6.txt 2>&1 || true
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT shardstate, COUNT(*) FROM pg_dist_shard_placement GROUP BY shardstate ORDER BY shardstate;" >> fase6.txt 2>&1 || true

echo "--- Subfase F: Verificación final ---" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT * FROM citus_get_active_worker_nodes();" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT COUNT(*) FROM usuario;" >> fase6.txt
docker exec -i citus_coordinator psql -U admin -d historia_clinica -c "SELECT DISTINCT shardstate FROM pg_dist_shard_placement;" >> fase6.txt

echo "Fase 6 completada."
