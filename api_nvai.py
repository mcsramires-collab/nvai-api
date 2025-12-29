from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import uvicorn
import base64

app = FastAPI()

SUPABASE_URL = "https://gbtvusyjolpautvyddvh.supabase.co"
SUPABASE_KEY = "sb_publishable_b1nsi_xHaSjm1BQbBToXIA_-6TaOtb5"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def decodificar_chave(chave):
    try:
        decoded = base64.b64decode(chave).decode('utf-8')
        # Formato: NVAI|CNPJ|NIVEL|TIME
        return decoded.split('|')
    except:
        return None

@app.post("/enviar_log")
async def receber_log(payload: dict, x_api_key: str = Header(None)):
    info = decodificar_chave(x_api_key)
    if not info or info[0] != "NVAI":
        raise HTTPException(status_code=401, detail="Chave Invalida")

    cnpj_empresa = info[1]
    nivel = info[2] # MASTER, SUPER ou USER

    # Busca empresa e custo do funcionário
    empresa = supabase.table("empresas").select("id").eq("cnpj", cnpj_empresa).execute()
    if not empresa.data:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    
    id_emp = empresa.data[0]["id"]
    func_id = payload.get("funcionario")

    # Busca config de custo (Salário/Horas)
    config = supabase.table("configuracoes_usuarios").select("*").eq("empresa_id", id_emp).eq("funcionario_id", func_id).execute()
    
    custo_min = 0
    if config.data:
        # Cálculo: (Salário / Horas Mensais) / 60 min
        custo_min = (config.data[0]['salario_mensal'] / config.data[0]['horas_mensais']) / 60

    registro = {
        "empresa_id": id_emp,
        "funcionario": func_id,
        "equipe": info[3] if len(info) > 3 else "Geral",
        "janela": payload.get("janela"),
        "cpu": payload.get("cpu"),
        "ram": payload.get("ram"),
        "ping": payload.get("ping"),
        "custo_minuto": custo_min
    }

    supabase.table("logs").insert(registro).execute()
    return {"status": "sucesso", "permissao": nivel}

if __name__ == "__main__":
    import os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
