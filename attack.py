import urllib.request
import json
import base64

db_url = "http://localhost:5984/historias_clinicas"
auth_b64 = base64.b64encode(b"admin:admin").decode("utf-8")
headers = {
    "Authorization": f"Basic {auth_b64}",
    "Content-Type": "application/json"
}

print("🔥 INICIANDO ATAQUE DE INTEGRIDAD (ISO 27001) 🔥")
print("1. Accediendo furtivamente al nodo interno de bases de datos de La Guajira (CouchDB puerto 5984)...")

try:
    req = urllib.request.Request(f"{db_url}/_all_docs?include_docs=true", headers=headers, method="GET")
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode('utf-8'))

    hacked = False
    for row in data.get("rows", []):
        doc = row.get("doc", {})
        if doc.get("resourceType") == "Bundle":
            entries = doc.get("entry", [])
            # Busco a nuestro paciente de prueba CARLOS123
            if len(entries) > 1 and entries[1].get("resource", {}).get("id") == "CARLOS123":
                print(f"2. Expediente Médico Encontrado -> ID: {doc['_id']}")
                print(f"   Firmado criptográficamente por Nodo: {doc.get('p2p_audit', {}).get('nodo_emisor')}")
                print("3. Ejecutando inyección: Modificando historia clínica SIN pasar por la API Gateway (By-pass)...")
                
                # EL ATAQUE: Cambiando nombre y género maliciosamente directo en la base de datos
                entries[1]["resource"]["name"] = [{"text": "Carlos HACKEADO (Diagnóstico Alterado)"}]
                entries[1]["resource"]["gender"] = "female"
                
                put_req = urllib.request.Request(
                    f"{db_url}/{doc['_id']}",
                    data=json.dumps(doc).encode('utf-8'),
                    headers=headers,
                    method="PUT"
                )
                urllib.request.urlopen(put_req)
                hacked = True
                print("================================================================")
                print("☠️  ATAQUE INYECTADO: BASE DE DATOS COMPROMETIDA EXITOSAMENTE")
                print("================================================================")
                print("Ve a la interfaz de React ahora mismo. En la tabla de monitor, este paciente debe aparecer en ROJO,")
                print("marcado como ⚠️ ADULTERADO, porque su hash actual no coincidirá con la firma original del backend.")
                break

    if not hacked:
        print("No se encontró a CARLOS123 en la base de datos. Se necesita lanzar la petición POST de creación primero.")
        
except Exception as e:
    print(f"Error realizando ataque: {e}")
