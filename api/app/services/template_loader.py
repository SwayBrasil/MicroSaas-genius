# api/app/services/template_loader.py
"""Carrega templates de texto do frontend/public/templates/ (ou frontend/public/images/templates/ para compatibilidade)"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Caminho base para templates (ajustar conforme necessário)
# Tenta primeiro em public/templates, depois em public/images/templates
BASE_PATH_NEW = Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "templates"
BASE_PATH_OLD = Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "images" / "templates"

# Fallback: tenta caminhos alternativos
FALLBACK_PATHS = [
    BASE_PATH_NEW,  # Nova estrutura: public/templates/
    BASE_PATH_OLD,  # Estrutura antiga: public/images/templates/
    Path("/app/frontend/public/templates"),  # Docker - nova
    Path("/app/frontend/public/images/templates"),  # Docker - antiga
    Path.cwd() / "frontend" / "public" / "templates",
    Path.cwd() / "frontend" / "public" / "images" / "templates",
    Path.cwd() / "public" / "templates",
    Path.cwd() / "public" / "images" / "templates",
]


def load_template(template_name: str) -> Optional[str]:
    """
    Carrega um template de texto.
    
    Args:
        template_name: Nome do template (ex: "fechamento-anual.txt", "planos-life.json")
    
    Returns:
        Conteúdo do template como string, ou None se não encontrado
    """
    for base_path in FALLBACK_PATHS:
        template_path = base_path / template_name
        if template_path.exists():
            try:
                if template_name.endswith(".json"):
                    # Se for JSON, retorna como string formatada
                    with open(template_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # Formata JSON para texto legível
                        if isinstance(data, dict):
                            # Para planos-life.json, formata os planos
                            if "mensal" in data and "anual" in data:
                                mensal = data["mensal"]
                                anual = data["anual"]
                                
                                # Novo formato: se tiver campo "texto", usa ele diretamente
                                if "texto" in mensal and "texto" in anual:
                                    mensal_texto = mensal.get("texto", "")
                                    anual_texto = anual.get("texto", "")
                                    pergunta = mensal.get("pergunta_final", anual.get("pergunta_final", ""))
                                    
                                    # Retorna mensal + anual + pergunta (se houver)
                                    result = f"""{mensal_texto}

---

{anual_texto}"""
                                    if pergunta:
                                        result += f"\n\n{pergunta}"
                                    return result
                                
                                # Formato antigo (fallback): apenas preço
                                pergunta = data.get("pergunta_final", mensal.get("pergunta_final", anual.get("pergunta_final", "")))
                                return f"""Plano Mensal – {mensal.get('preco', 'R$69,90')}

Plano Anual – {anual.get('preco', 'R$598,80 (ou 12x de R$49,90)')}

{pergunta}"""
                            return json.dumps(data, ensure_ascii=False, indent=2)
                        return str(data)
                else:
                    # Arquivo de texto simples
                    with open(template_path, "r", encoding="utf-8") as f:
                        return f.read().strip()
            except Exception as e:
                print(f"⚠️ Erro ao carregar template {template_name}: {e}")
                continue
    
    print(f"⚠️ Template não encontrado: {template_name}")
    return None


def get_audio_path(audio_id: str) -> Optional[str]:
    """
    Retorna o caminho do arquivo de áudio baseado no audio_id.
    
    Args:
        audio_id: ID do áudio (ex: "audio2_inconstancia", "01-boas-vindas-qualificacao")
    
    Returns:
        Caminho relativo do arquivo (ex: "/audios/funil-longo/01-boas-vindas-qualificacao.opus")
        ou None se não encontrado
    """
    # Mapeamento de audio_id para arquivo
    audio_map: Dict[str, str] = {
        # Funil Longo - FASE 1 (Boas-vindas)
        "audio1_boas_vindas": "/audios/funil-longo/01-boas-vindas-qualificacao.opus",
        "life_funil_longo_01_boas_vindas_e_qualificacao_inicial": "/audios/funil-longo/01-boas-vindas-qualificacao.opus",
        # Funil Longo - FASE 2 (Dores) - Temporário: todos usam o mesmo arquivo até ter os 5 específicos
        "audio2_inconstancia": "/audios/funil-longo/02-dor-generica.opus",
        "audio2_barriga_inchaco": "/audios/funil-longo/02-dor-generica.opus",
        "audio2_rotina_corrida": "/audios/funil-longo/02-dor-generica.opus",
        "audio2_resultado_avancado": "/audios/funil-longo/02-dor-generica.opus",
        "audio2_compulsao_doces": "/audios/funil-longo/02-dor-generica.opus",
        "life_funil_longo_02_dor_generica": "/audios/funil-longo/02-dor-generica.opus",
        # Funil Longo - FASE 3 (Planos)
        "audio3_explicacao_planos": "/audios/funil-longo/03-explicacao-planos.opus",
        "life_funil_longo_03_explicacao_planos": "/audios/funil-longo/03-explicacao-planos.opus",
        # Funil Longo - FASE 4 (Recuperação)
        "audio4_recuperacao": "/audios/funil-longo/04-recuperacao-pos-nao-compra.opus",
        "life_funil_longo_04_recuperacao_pos_nao_compra": "/audios/funil-longo/04-recuperacao-pos-nao-compra.opus",
        # Mini Funil BF
        "audio_bf_oferta": "/audios/mini-funil-bf/01-oferta-black-friday.opus",
        "life_mini_funil_bf_01_oferta_black_friday": "/audios/mini-funil-bf/01-oferta-black-friday.opus",
        "audio_bf_followup": "/audios/mini-funil-bf/02-followup-sem-resposta.opus",
        "life_mini_funil_bf_02_followup_sem_resposta": "/audios/mini-funil-bf/02-followup-sem-resposta.opus",
        # Recuperação 50%
        "audio_recuperacao_50_1": "/audios/recuperacao-50/02-audio-followup.opus",
        "life_recuperacao_50_02_audio_followup": "/audios/recuperacao-50/02-audio-followup.opus",
        "audio_recuperacao_50_2": "/audios/recuperacao-50/03-audio-ultimo-chamado.opus",
        "life_recuperacao_50_03_audio_ultimo_chamado": "/audios/recuperacao-50/03-audio-ultimo-chamado.opus",
    }
    
    # Se o audio_id já é um caminho, retorna direto
    if audio_id.startswith("/audios/"):
        return audio_id
    
    # Busca no mapa
    return audio_map.get(audio_id)


def get_template_by_code(template_code: str) -> Optional[str]:
    """
    Carrega template por código interno.
    
    Args:
        template_code: Código do template (ex: "life_funil_longo_plano_anual")
    
    Returns:
        Conteúdo do template ou None
    """
    template_map: Dict[str, str] = {
        "life_funil_longo_plano_anual": "fechamento-anual.txt",
        "life_funil_longo_plano_mensal": "fechamento-mensal.txt",
        "life_funil_longo_planos": "planos-life.json",
        "life_recuperacao_50_01_texto_oferta_50": "recuperacao-50-oferta.txt",
        "life_pos_compra": "pos-compra-life.txt",
        "planos_life": "planos-life.json",
        "planos-life": "planos-life.json",  # Alias
        "fechamento-anual": "fechamento-anual.txt",  # Alias
        "fechamento-mensal": "fechamento-mensal.txt",  # Alias
        "recuperacao-50-oferta": "recuperacao-50-oferta.txt",  # Alias
        "pos-compra-life": "pos-compra-life.txt",  # Alias
    }
    
    filename = template_map.get(template_code)
    if filename:
        return load_template(filename)
    
    return None

