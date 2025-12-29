from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import uvicorn
import base64
import unicodedata
import os

app = FastAPI(title="NVAI Enterprise API")

# ====================================================
# CONFIGURAÇÃO SUPABASE
# ====================================================
SUPABASE_URL = "SUA_URL_DO_SUPABASE" 
SUPABASE_KEY = "SUA_PUBLISHABLE_ANON_KEY"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def decodificar_chave(chave):
    try:
        # Formato esperado após decode: NVAI|CNPJ|NIVEL|EQUIPE
        decoded = base64.b64decode(chave).decode('utf-8')
        return decoded.split('|')
    except:
        return None

def limpar_texto(texto):
    if not texto: return "Ocioso"
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).encode('ascii', 'ignore').decode('ascii')

@app.get("/")
async def root():
    return {"status": "NVAI Enterprise Online"}

@app.post("/enviar_log")
async def receber_log(payload: dict, x_api_key: str = Header(None)):
    info_chave = decodificar_chave(x_api_key)
    
    if not info_chave or info_chave[0] != "NVAI":
        raise HTTPException(status_code=401, detail="Chave NVAI Invalida ou Corrompida")

    cnpj_empresa = info_chave[1]
    nivel_acesso = info_chave[2] # MASTER, SUPER ou USER
    equipe_nome = info_chave[3] if len(info_chave) > 3 else "Geral"

    # 1. Busca a empresa pelo CNPJ
    empresa = supabase.table("empresas").select("id").eq("cnpj", cnpj_empresa).execute()
    if not empresa.data:
        raise HTTPException(status_code=404, detail="Empresa nao cadastrada no sistema")
    
    id_emp = empresa.data[0]["id"]
    func_id = payload.get("funcionario")

    # 2. Busca configuração de custo (Cálculo de Ociosidade)
    # Tabela: configuracoes_usuarios (funcionario_id, salario_mensal, horas_mensais)
    config = supabase.table("configuracoes_usuarios").select("*").eq("empresa_id", id_emp).eq("funcionario_id", func_id).execute()
    
    custo_min = 0
    if config.data:
        # Cálculo: (Salário / Horas Mensais) / 60 minutos
        salario = config.data[0].get('salario_mensal', 0)
        horas = config.data[0].get('horas_mensais', 220)
        custo_min = (salario / horas) / 60

    # 3. Monta o registro final
    registro = {
        "empresa_id": id_emp,
        "funcionario": limpar_texto(func_id),
        "equipe": equipe_nome,
        "janela": limpar_texto(payload.get("janela")),
        "cpu": float(payload.get("cpu", 0)),
        "ram": float(payload.get("ram", 0)),
        "ping": float(payload.get("ping", 0)),
        "custo_minuto": custo_min,
        "nivel_origem": nivel_acesso
    }

    try:
        supabase.table("logs").insert(registro).execute()
        # Retorna o intervalo de 5 min (300 seg) para o robô esperar
        return {"status": "sucesso", "intervalo_s": 300, "comando": "CONTINUAR"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
