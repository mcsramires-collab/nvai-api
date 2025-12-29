from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import uvicorn
import base64
import unicodedata
import os

app = FastAPI(title="NVAI Global SaaS API")

# ====================================================
# CONFIGURAÇÃO SUPABASE
# ====================================================
# Certifique-se de preencher com suas credenciais reais do Supabase
SUPABASE_URL = "https://gbtvusyjolpautvyddvh.supabase.co"
SUPABASE_KEY = "sb_publishable_b1nsi_xHaSjm1BQbBToXIA_-6TaOtb5"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================================================
# UTILITÁRIOS
# ====================================================
def decodificar_chave(chave):
    """Decodifica a chave Base64: NVAI|CNPJ|NIVEL|EQUIPE"""
    try:
        decoded = base64.b64decode(chave).decode('utf-8')
        return decoded.split('|')
    except:
        return None

def limpar_texto(texto):
    """Sanitiza strings para evitar erros de caracteres especiais no banco."""
    if not texto: return "Ocioso"
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).encode('ascii', 'ignore').decode('ascii')

# ====================================================
# ROTAS DA API
# ====================================================

@app.get("/")
async def root():
    return {"status": "NVAI SaaS Gateway Online", "versao": "4.1.0"}

@app.post("/ativar")
async def ativar_licenca(dados: dict):
    """
    Rota para o primeiro acesso. 
    Vincula a chave de ativação ao hardware_id (UUID) da máquina.
    """
    chave = dados.get("chave")
    hw_id = dados.get("hw_id")

    if not chave or not hw_id:
        raise HTTPException(status_code=400, detail="Chave e HW_ID obrigatorios")

    # 1. Verifica se a licença existe na tabela 'licencas'
    licenca_query = supabase.table("licencas").select("*").eq("chave_ativacao", chave).execute()
    
    if not licenca_query.data:
        raise HTTPException(status_code=401, detail="Chave de ativacao inexistente")
    
    lic = licenca_query.data[0]
    
    # 2. Verifica se a chave já está vinculada a OUTRO computador
    if lic['status'] == 'vinculado' and lic['hardware_id'] != hw_id:
        raise HTTPException(status_code=403, detail="Esta chave ja esta sendo usada em outra maquina")

    # 3. Verifica se a licença ou a empresa estão suspensas
    if lic['status'] == 'suspenso':
        raise HTTPException(status_code=403, detail="Chave suspensa por inadimplencia")

    # 4. Vincula o hardware e ativa o status
    try:
        supabase.table("licencas").update({
            "hardware_id": hw_id, 
            "status": "vinculado"
        }).eq("chave_ativacao", chave).execute()
        
        return {"status": "sucesso", "mensagem": "Licenca ativada e vinculada ao hardware"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao vincular licenca: {str(e)}")

@app.post("/enviar_log")
async def receber_log(payload: dict, x_api_key: str = Header(None)):
    """
    Recebe logs periódicos. 
    Valida a chave, o hardware e o status da assinatura.
    """
    info_chave = decodificar_chave(x_api_key)
    hw_id_cliente = payload.get("hw_id")
    
    if not info_chave or info_chave[0] != "NVAI":
        raise HTTPException(status_code=401, detail="Chave NVAI Invalida")

    cnpj_empresa = info_chave[1]
    
    # 1. Validação cruzada: Chave vs Hardware no banco
    validacao = supabase.table("licencas").select("status, hardware_id, empresa_id").eq("chave_ativacao", x_api_key).execute()
    
    if not validacao.data:
        raise HTTPException(status_code=401, detail="Licenca nao localizada")
    
    lic_status = validacao.data[0]
    
    # Bloqueio remoto: Se o status não for 'vinculado' ou hardware divergir, mata o robô
    if lic_status['status'] != 'vinculado' or lic_status['hardware_id'] != hw_id_cliente:
        return {"status": "erro", "comando": "DESATIVAR", "motivo": "Licenca Invalida ou Suspensa"}

    # 2. Busca dados financeiros para cálculo de ociosidade
    id_emp = lic_status['empresa_id']
    func_id = payload.get("funcionario")
    
    config = supabase.table("configuracoes_usuarios").select("*").eq("empresa_id", id_emp).eq("funcionario_id", func_id).execute()
    
    custo_min = 0
    if config.data:
        salario = config.data[0].get('salario_mensal', 0)
        horas = config.data[0].get('horas_mensais', 220)
        custo_min = (salario / horas) / 60

    # 3. Gravação do log
    registro = {
        "empresa_id": id_emp,
        "funcionario": limpar_texto(func_id),
        "equipe": info_chave[3] if len(info_chave) > 3 else "Geral",
        "janela": limpar_texto(payload.get("janela")),
        "cpu": float(payload.get("cpu", 0)),
        "ram": float(payload.get("ram", 0)),
        "custo_minuto": custo_min,
        "nivel_origem": info_chave[2]
    }

    try:
        supabase.table("logs").insert(registro).execute()
        return {"status": "sucesso", "intervalo_s": 300, "comando": "CONTINUAR"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de Gravacao: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
