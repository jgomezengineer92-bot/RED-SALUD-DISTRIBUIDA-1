#!/bin/bash
echo "🔥 INICIANDO TEST DE CAOS (CHAOS ENGINEERING) 🔥"
echo "Destruyendo pods aleatoriamente para verificar auto-recuperación de Minikube..."

while true; do
  # Seleccionamos una región al azar
  NODES=("guajira-api" "amazonas-api" "guainia-api" "narino-api")
  RANDOM_INDEX=$(( RANDOM % 4 ))
  TARGET_NODE=${NODES[$RANDOM_INDEX]}
  
  echo "☠️ Matando pod(s) con label app=$TARGET_NODE"
  kubectl delete pod -l app=$TARGET_NODE
  
  # Esperar un tiempo prudencial antes de matar el siguiente
  sleep 20
done
